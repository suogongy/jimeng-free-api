import json
import uuid
import time
import requests
from typing import Dict, List, Optional, Union
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import hashlib
from urllib.parse import quote
import logging
import sys

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('api_debug.log')
    ]
)
logger = logging.getLogger('jimeng_api')

DEFAULT_ASSISTANT_ID = "513695"
DEFAULT_MODEL = "high_aes_general_v30l:general_v3.0_18b"
DRAFT_VERSION = "3.0.2"
VERSION_CODE = "5.8.0"
PLATFORM_CODE = "7"
DEVICE_ID = str(int(time.time() * 1000) % 100000000 + 2500000000)
DEFAULT_WEB_ID = str(int(time.time() * 1000) % 100000000 + 2500000000)

# 伪装headers
FAKE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-language": "zh-CN,zh;q=0.9",
    "Cache-control": "no-cache",
    "Last-event-id": "undefined",
    "Appid": DEFAULT_ASSISTANT_ID,
    "Appvr": VERSION_CODE,
    "Origin": "https://jimeng.jianying.com",
    "Pragma": "no-cache",
    "Priority": "u=1, i",
    "Referer": "https://jimeng.jianying.com",
    "Pf": PLATFORM_CODE,
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

MODEL_MAP = {
    "high_aes_general_v30l": "high_aes_general_v30l:general_v3.0_18b",
    "high_aes_general_v30l:general_v3.0_18b": "high_aes_general_v30l:general_v3.0_18b",
}

def get_model(model_name):
    return MODEL_MAP.get(model_name, DEFAULT_MODEL)

def get_device_time():
    return int(time.time())

def generate_sign(uri, device_time):
    # 使用uri的最后7个字符
    uri_part = uri[-7:]
    sign_str = f"9e2c|{uri_part}|{PLATFORM_CODE}|{VERSION_CODE}|{device_time}||11ac"
    return hashlib.md5(sign_str.encode()).hexdigest()

def generate_cookie(refresh_token):
    web_id = DEFAULT_WEB_ID
    user_id = str(uuid.uuid4()).replace('-', '')
    timestamp = int(time.time())
    expire_time = timestamp + 5184000  # 60天
    
    return [
        f"_tea_web_id={web_id}",
        "is_staff_user=false",
        "store-region=cn-gd",
        "store-region-src=uid",
        f"sid_guard={refresh_token}%7C{timestamp}%7C5184000%7CMon%2C+03-Feb-2025+08%3A17%3A09+GMT",
        f"uid_tt={user_id}",
        f"uid_tt_ss={user_id}",
        f"sid_tt={refresh_token}",
        f"sessionid={refresh_token}",
        f"sessionid_ss={refresh_token}",
        f"sid_tt={refresh_token}"
    ]

def get_common_params(refresh_token, uri):
    logger.debug(f"开始生成通用参数 - URI: {uri}")
    device_time = get_device_time()
    sign = generate_sign(uri, device_time)
    
    headers = {
        **FAKE_HEADERS,
        "Cookie": "; ".join(generate_cookie(refresh_token)),
        "Device-Time": str(device_time),
        "Sign": sign,
        "Sign-Ver": "1"
    }
    
    params = {
        "aid": DEFAULT_ASSISTANT_ID,
        "device_platform": "web",
        "region": "CN",
        "web_id": DEFAULT_WEB_ID
    }
    
    logger.debug(f"生成的请求头: {json.dumps(headers, ensure_ascii=False)}")
    logger.debug(f"生成的参数: {json.dumps(params, ensure_ascii=False)}")
    return headers, params

def get_credit(refresh_token):
    logger.info("开始获取信用额度")
    uri = "/commerce/v1/benefits/user_credit"
    headers, params = get_common_params(refresh_token, uri)
    
    try:
        # 创建会话并配置重试策略
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # 移除Accept-Encoding头，避免服务器返回压缩响应
        headers.pop('Accept-Encoding', None)
        
        response = session.post(
            f"https://jimeng.jianying.com{uri}",
            headers=headers,
            params=params,
            json={},
            timeout=15
        )
        
        logger.debug(f"信用额度请求URL: {response.url}")
        logger.debug(f"信用额度请求头: {json.dumps(dict(response.request.headers), ensure_ascii=False)}")
        logger.debug(f"信用额度响应状态码: {response.status_code}")
        
        # 检查响应编码
        if response.encoding is None:
            response.encoding = 'utf-8'
            
        # 记录原始响应内容
        raw_content = response.content
        logger.debug(f"原始响应内容: {raw_content}")
        
        if response.status_code != 200:
            logger.error(f"获取信用额度失败: {response.text}")
            raise Exception(f"获取信用额度失败: {response.text}")
        
        # 处理响应数据
        try:
            # 尝试直接解析JSON
            data = response.json()
        except json.JSONDecodeError:
            # 如果JSON解析失败，尝试解码响应内容
            try:
                # 尝试使用不同的编码方式解码
                decoded_content = raw_content.decode('utf-8')
                logger.debug(f"解码后的响应内容: {decoded_content}")
                data = json.loads(decoded_content)
            except Exception as e:
                logger.error(f"响应内容解码失败: {str(e)}")
                logger.error(f"原始响应内容: {raw_content}")
                raise Exception(f"响应内容解码失败: {str(e)}")
            
        if not isinstance(data, dict):
            logger.error(f"获取信用额度失败: 响应格式错误")
            raise Exception("获取信用额度失败: 响应格式错误")
            
        # 检查响应状态
        if data.get("ret") != "0":
            logger.error(f"获取信用额度失败: {data.get('errmsg')}")
            raise Exception(f"获取信用额度失败: {data.get('errmsg')}")
            
        # 从data字段获取信用信息
        credit_data = data.get("data", {}).get("credit", {})
        gift_credit = credit_data.get("gift_credit", 0)
        purchase_credit = credit_data.get("purchase_credit", 0)
        vip_credit = credit_data.get("vip_credit", 0)
        total_credit = gift_credit + purchase_credit + vip_credit
        
        logger.info(f"积分信息: 赠送积分: {gift_credit}, 购买积分: {purchase_credit}, VIP积分: {vip_credit}, 总积分: {total_credit}")
        
        return {
            "gift_credit": gift_credit,
            "purchase_credit": purchase_credit,
            "vip_credit": vip_credit,
            "total_credit": total_credit
        }
    except Exception as e:
        logger.error(f"获取信用额度时发生异常: {str(e)}")
        raise

def receive_credit(refresh_token):
    logger.info("开始领取信用额度")
    uri = "/commerce/v1/benefits/credit_receive"
    headers, params = get_common_params(refresh_token, uri)
    
    try:
        response = requests.post(
            f"https://jimeng.jianying.com{uri}",
            headers=headers,
            params=params,
            json={"time_zone": "Asia/Shanghai"},
            timeout=15
        )
        
        logger.debug(f"领取信用额度请求URL: {response.url}")
        logger.debug(f"领取信用额度请求头: {json.dumps(dict(response.request.headers), ensure_ascii=False)}")
        logger.debug(f"领取信用额度响应状态码: {response.status_code}")
        logger.debug(f"领取信用额度响应内容: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"领取信用额度失败: {response.text}")
            raise Exception(f"领取信用额度失败: {response.text}")
        
        data = response.json()
        if not isinstance(data, dict):
            logger.error(f"领取信用额度失败: 响应格式错误")
            raise Exception("领取信用额度失败: 响应格式错误")
            
        cur_total_credits = data.get("cur_total_credits", 0)
        receive_quota = data.get("receive_quota", 0)
        
        logger.info(f"今日{receive_quota}积分收取成功，剩余积分: {cur_total_credits}")
        
        return {
            "cur_total_credits": cur_total_credits,
            "receive_quota": receive_quota
        }
    except Exception as e:
        logger.error(f"领取信用额度时发生异常: {str(e)}")
        raise

def generate_images(prompt: str, refresh_token: str = None, sample_strength: float = 0.5, width: int = 1664, height: int = 936, seed: int = int(DEFAULT_WEB_ID)) -> dict:
    try:
        logger.info(f"开始生成图片 - 模型: {DEFAULT_MODEL}, 提示词: {prompt}, 尺寸: 1024x1024, 精细度: 0.5")
        
        # 获取信用额度
        credit_info = get_credit(refresh_token)
        if not credit_info:
            return {"status": "error", "message": "获取信用额度失败"}
            
        total_credit = credit_info.get("gift_credit", 0) + credit_info.get("purchase_credit", 0) + credit_info.get("vip_credit", 0)
        if total_credit < 1:
            return {"status": "error", "message": "信用额度不足"}
            
        # 生成图片
        uri = "/mweb/v1/aigc_draft/generate"
        headers, params = get_common_params(refresh_token, uri)
        
        # 移除Accept-Encoding头，避免服务器返回压缩响应
        headers.pop('Accept-Encoding', None)
        
        # 添加babi_param参数
        babi_param = {
            "scenario": "image_video_generation",
            "feature_key": "aigc_to_image",
            "feature_entrance": "to_image",
            "feature_entrance_detail": f"to_image-{DEFAULT_MODEL}"
        }
        params["babi_param"] = json.dumps(babi_param)
        
        # 生成请求数据
        submit_id = str(uuid.uuid4())
        draft_id = str(uuid.uuid4())
        component_id = str(uuid.uuid4())
        ability_id = str(uuid.uuid4())
        generate_id = str(uuid.uuid4())
        core_param_id = str(uuid.uuid4())
        history_option_id = str(uuid.uuid4())
        large_image_info_id = str(uuid.uuid4())
        
        data = {
            "extend": {
                "root_model": DEFAULT_MODEL,
                "template_id": ""
            },
            "submit_id": submit_id,
            "metrics_extra": json.dumps({
                "templateId": "",
                "generateCount": 2,
                "promptSource": "custom",
                "templateSource": "",
                "lastRequestId": "",
                "originRequestId": ""
            }),
            "draft_content": json.dumps({
                "type": "draft",
                "id": draft_id,
                "min_version": "3.0.2",
                "min_features": [],
                "is_from_tsn": True,
                "version": "3.1.5",
                "main_component_id": component_id,
                "component_list": [{
                    "type": "image_base_component",
                    "id": component_id,
                    "min_version": "3.0.2",
                    "generate_type": "generate",
                    "aigc_mode": "workbench",
                    "abilities": {
                        "type": "",
                        "id": ability_id,
                        "generate": {
                            "type": "",
                            "id": generate_id,
                            "core_param": {
                                "type": "",
                                "id": core_param_id,
                                "model": DEFAULT_MODEL,
                                "prompt": prompt,
                                "negative_prompt": "",
                                "seed": seed,
                                "sample_strength": sample_strength,
                                "image_ratio": 1,
                                "large_image_info": {
                                    "type": "",
                                    "id": large_image_info_id,
                                    "height": height,
                                    "width": width,
                                    "resolution_type": "1k"
                                }
                            },
                            "history_option": {
                                "type": "",
                                "id": history_option_id
                            }
                        }
                    }
                }]
            })
        }
        
        # 发送生成请求
        response = requests.post(
            f"https://jimeng.jianying.com{uri}",
            headers=headers,
            params=params,
            json=data
        )
        
        logger.debug(f"生成图片请求URL: {response.url}")
        logger.debug(f"生成图片请求头: {json.dumps(dict(response.request.headers), ensure_ascii=False)}")
        logger.debug(f"生成图片请求体: {json.dumps(data, ensure_ascii=False)}")
        logger.debug(f"生成图片响应状态码: {response.status_code}")
        logger.debug(f"生成图片响应内容: {response.text}")
        
        if response.status_code != 200:
            return {"status": "error", "message": f"生成图片失败: {response.status_code}"}
            
        result = response.json()
        if result.get("ret") != "0":
            return {"status": "error", "message": f"生成图片失败: {result.get('errmsg')}"}
            
        return {"status": "success", "data": result.get("data", {})}
        
    except Exception as e:
        logger.error(f"生成图片时发生异常: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_history_by_ids(refresh_token: str, history_record_ids: List[str], max_retries: int = 30, retry_interval: int = 2) -> Dict:
    """
    根据history_record_id获取生成图片的结果
    
    Args:
        refresh_token: 刷新令牌
        history_record_ids: 历史记录ID列表
        max_retries: 最大重试次数
        retry_interval: 重试间隔(秒)
    
    Returns:
        Dict: 包含生成图片结果的字典
    """
    try:
        uri = "/mweb/v1/get_history_by_ids"
        headers, params = get_common_params(refresh_token, uri)
        
        # 移除Accept-Encoding头，避免服务器返回压缩响应
        headers.pop('Accept-Encoding', None)
        
        # 根据images.ts中的实现修改请求数据
        data = {
            "history_ids": history_record_ids,
            "image_info": {
                "width": 2048,
                "height": 2048,
                "format": "webp",
                "image_scene_list": [
                    {
                        "scene": "smart_crop",
                        "width": 360,
                        "height": 360,
                        "uniq_key": "smart_crop-w:360-h:360",
                        "format": "webp",
                    },
                    {
                        "scene": "smart_crop",
                        "width": 480,
                        "height": 480,
                        "uniq_key": "smart_crop-w:480-h:480",
                        "format": "webp",
                    },
                    {
                        "scene": "smart_crop",
                        "width": 720,
                        "height": 720,
                        "uniq_key": "smart_crop-w:720-h:720",
                        "format": "webp",
                    },
                    {
                        "scene": "normal",
                        "width": 2400,
                        "height": 2400,
                        "uniq_key": "2400",
                        "format": "webp",
                    },
                    {
                        "scene": "normal",
                        "width": 1080,
                        "height": 1080,
                        "uniq_key": "1080",
                        "format": "webp",
                    },
                    {
                        "scene": "normal",
                        "width": 720,
                        "height": 720,
                        "uniq_key": "720",
                        "format": "webp",
                    },
                    {
                        "scene": "normal",
                        "width": 480,
                        "height": 480,
                        "uniq_key": "480",
                        "format": "webp",
                    },
                    {
                        "scene": "normal",
                        "width": 360,
                        "height": 360,
                        "uniq_key": "360",
                        "format": "webp",
                    }
                ]
            },
            "http_common_info": {
                "aid": int(DEFAULT_ASSISTANT_ID)
            }
        }
        
        # 完全对应images.ts逻辑的状态变量
        status = 20  # 初始状态: 20（生成中）
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"https://jimeng.jianying.com{uri}",
                    headers=headers,
                    params=params,
                    json=data
                )
                
                logger.debug(f"获取图片结果请求URL: {response.url}")
                logger.debug(f"获取图片结果请求头: {json.dumps(dict(response.request.headers), ensure_ascii=False)}")
                logger.debug(f"获取图片结果请求体: {json.dumps(data, ensure_ascii=False)}")
                logger.debug(f"获取图片结果响应状态码: {response.status_code}")
                logger.debug(f"获取图片结果响应内容: {response.text}")
                
                if response.status_code != 200:
                    raise Exception(f"获取图片结果失败: {response.status_code}")
                    
                result = response.json()
                if result.get("ret") != "0":
                    raise Exception(f"获取图片结果失败: {result.get('errmsg')}")
                
                # 严格按照images.ts中的处理逻辑获取结果
                history_id = history_record_ids[0]
                if not result.get("data", {}).get(history_id):
                    raise Exception("记录不存在")
                    
                history_data = result["data"][history_id]
                status = history_data.get("status")
                fail_code = history_data.get("fail_code")
                item_list = history_data.get("item_list", [])
                
                logger.debug(f"图片生成状态: {status}, 失败代码: {fail_code}, 项目列表: {item_list}")
                
                # 与images.ts保持完全一致的状态检查
                if status == 50:  # 完成
                    return result
                elif status == 30:  # 失败
                    if fail_code == '2038':
                        raise Exception("内容被过滤")
                    else:
                        raise Exception("图片生成失败")
                elif status == 20:  # 生成中
                    if attempt < max_retries - 1:
                        logger.info(f"图片生成中，等待{retry_interval}秒后重试...")
                        time.sleep(retry_interval)
                    else:
                        raise Exception("图片生成超时")
                else:
                    raise Exception(f"未知的图片生成状态: {status}")
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"获取图片结果失败，重试中... ({str(e)})")
                time.sleep(retry_interval)
                
    except Exception as e:
        logger.error(f"获取图片结果时发生异常: {str(e)}")
        raise

def generate_images_with_result(prompt: str, width: int = 1664, height: int = 936, refresh_token: str = None, seed: int = int(DEFAULT_WEB_ID), sample_strength: float = 0.5) -> dict:
    """
    生成图片并等待获取结果
    
    Args:
        prompt: 提示词
        refresh_token: 刷新令牌
    
    Returns:
        dict: 包含生成图片结果的字典
    """
    try:
        # 首先调用生成图片接口
        generate_result = generate_images(prompt, refresh_token, sample_strength, width, height, seed)
        if generate_result.get("status") != "success":
            return generate_result
            
        # 获取history_record_id
        history_record_id = generate_result.get("data", {}).get("aigc_data", {}).get("history_record_id")
        if not history_record_id:
            return {"status": "error", "message": "未获取到history_record_id"}
            
        # 直接调用get_history_by_ids方法获取结果
        result = get_history_by_ids(refresh_token, [history_record_id])
        
        # 提取图片URL列表，参考images.ts中的处理逻辑
        image_urls = []
        if result.get("data", {}).get(history_record_id):
            item_list = result["data"][history_record_id].get("item_list", [])
            for item in item_list:
                image_url = None
                # 判断是否存在large_images及其image_url
                if (item.get("image") and 
                    item["image"].get("large_images") and 
                    len(item["image"]["large_images"]) > 0 and 
                    item["image"]["large_images"][0].get("image_url")):
                    image_url = item["image"]["large_images"][0]["image_url"]
                else:
                    # 如果没有large_images，则尝试使用cover_url
                    if item.get("common_attr") and item["common_attr"].get("cover_url"):
                        image_url = item["common_attr"]["cover_url"]
                
                # 只添加非空URL
                if image_url:
                    image_urls.append(image_url)
            
            logger.info(f"成功获取到{len(image_urls)}个图片URL")
        else:
            logger.warning(f"响应中未找到history_id: {history_record_id}")
            
        return {
            "status": "success",
            "image_urls": image_urls,
            "raw_response": result  # 保留原始响应，以便调试
        }
        
    except Exception as e:
        logger.error(f"生成图片并获取结果时发生异常: {str(e)}")
        return {"status": "error", "message": str(e)}

def main(
    prompt: str,
    width: int = 1664,
    height: int = 936,
    sample_strength: float = 0.5,
    refresh_token: str = "",
    seed: int = int(DEFAULT_WEB_ID)
) -> Dict[str, Union[List[str], str]]:
    """
    主函数，用于调用图像生成功能
    
    Args:
        prompt: 提示词
        width: 图像宽度
        height: 图像高度
        sample_strength: 采样强度
        refresh_token: 刷新令牌
        seed: 种子
    
    Returns:
        Dict[str, Union[List[str], str]]: 包含生成图像URL列表和状态信息的字典
    """
    try:
        # 直接使用生成图片并获取结果的函数
        result = generate_images_with_result(
            prompt=prompt,
            refresh_token=refresh_token,
            width=width,
            height=height,
            seed=seed,
            sample_strength=sample_strength
        )
        
        if result.get("status") != "success":
            return result
        
        image_urls = result.get("image_urls", [])
        
        if not image_urls:
            logger.warning("未能获取有效的图片URL")
            return {
                "status": "error",
                "message": "未能获取有效的图片URL"
            }
            
        return {
            "status": "success",
            "image_urls": image_urls
        }
    except Exception as e:
        logger.error(f"生成图片时发生异常: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    try:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 测试生成图片
        logger.info("开始测试图片生成")
        refresh_token = "f49656b2cc345895a880ba2c026c80ff"  # 使用有效的 refresh_token
        result = main(
            prompt="一只可爱的猫咪",
            refresh_token=refresh_token
        )
        logger.info(f"生成结果: {result}")
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}") 