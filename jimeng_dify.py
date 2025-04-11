import json
import uuid
import time
import requests
from typing import Dict
import hashlib
import datetime

# 移除logging相关导入和配置
def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 常量定义
DEFAULT_ASSISTANT_ID = "513695"
DEFAULT_MODEL = "high_aes_general_v30l:general_v3.0_18b"
VERSION_CODE = "5.8.0"
PLATFORM_CODE = "7"
DEFAULT_WEB_ID = str(int(time.time() * 1000) % 100000000 + 2500000000)

# 伪装headers
FAKE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
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
    
    return headers, params

def get_credit(refresh_token):
    uri = "/commerce/v1/benefits/user_credit"
    headers, params = get_common_params(refresh_token, uri)
    
    # 移除Accept-Encoding头，避免服务器返回压缩响应
    headers.pop('Accept-Encoding', None)
    
    print(f"[{get_current_time()}] [INFO] 开始请求用户信用额度: GET {uri}")
    print(f"[{get_current_time()}] [INFO] 请求参数: {params}")
    
    response = requests.post(
        f"https://jimeng.jianying.com{uri}",
        headers=headers,
        params=params,
        json={},
        timeout=15
    )
    
    if response.status_code != 200:
        print(f"[{get_current_time()}] [ERROR] 获取信用额度失败: 状态码 {response.status_code}, 响应: {response.text}")
        raise Exception(f"获取信用额度失败: {response.text}")
    
    data = response.json()
    print(f"[{get_current_time()}] [INFO] 信用额度响应: {json.dumps(data, ensure_ascii=False)}")
    
    if not isinstance(data, dict) or data.get("ret") != "0":
        print(f"[{get_current_time()}] [ERROR] 获取信用额度失败: {data.get('errmsg')}")
        raise Exception(f"获取信用额度失败: {data.get('errmsg')}")
        
    # 从data字段获取信用信息
    credit_data = data.get("data", {}).get("credit", {})
    gift_credit = credit_data.get("gift_credit", 0)
    purchase_credit = credit_data.get("purchase_credit", 0)
    vip_credit = credit_data.get("vip_credit", 0)
    total_credit = gift_credit + purchase_credit + vip_credit
    
    print(f"[{get_current_time()}] [INFO] 用户信用额度: 总额度={total_credit}, 赠送={gift_credit}, 购买={purchase_credit}, VIP={vip_credit}")
    
    return {
        "gift_credit": gift_credit,
        "purchase_credit": purchase_credit,
        "vip_credit": vip_credit,
        "total_credit": total_credit
    }

def generate_images(prompt, refresh_token, sample_strength, width, height, seed):
    # 获取信用额度
    print(f"[{get_current_time()}] [INFO] 开始获取用户信用额度")
    credit_info = get_credit(refresh_token)
    total_credit = credit_info.get("total_credit", 0)
    if total_credit < 1:
        print(f"[{get_current_time()}] [ERROR] 用户信用额度不足: {total_credit}")
        return {"status": "error", "message": "信用额度不足"}
        
    # 生成图片
    uri = "/mweb/v1/aigc_draft/generate"
    headers, params = get_common_params(refresh_token, uri)
    
    # 移除Accept-Encoding头
    headers.pop('Accept-Encoding', None)
    
    # 添加babi_param参数
    babi_param = {
        "scenario": "image_video_generation",
        "feature_key": "aigc_to_image",
        "feature_entrance": "to_image",
        "feature_entrance_detail": f"to_image-{DEFAULT_MODEL}"
    }
    params["babi_param"] = json.dumps(babi_param)
    
    print(f"[{get_current_time()}] [INFO] 开始生成图片: POST {uri}")
    print(f"[{get_current_time()}] [INFO] 提示词: {prompt}")
    print(f"[{get_current_time()}] [INFO] 参数: 宽度={width}, 高度={height}, 采样强度={sample_strength}, 种子={seed}")
    
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
    
    print(f"[{get_current_time()}] [INFO] 请求参数: {params}")
    
    response = requests.post(
        f"https://jimeng.jianying.com{uri}",
        headers=headers,
        params=params,
        json=data
    )
    
    if response.status_code != 200:
        print(f"[{get_current_time()}] [ERROR] 生成图片请求失败: 状态码 {response.status_code}, 响应: {response.text}")
        return {"status": "error", "message": f"生成图片失败: {response.status_code}"}
        
    result = response.json()
    print(f"[{get_current_time()}] [INFO] 生成图片响应: {json.dumps(result, ensure_ascii=False)}")
    
    if result.get("ret") != "0":
        print(f"[{get_current_time()}] [ERROR] 生成图片失败: {result.get('errmsg')}")
        return {"status": "error", "message": f"生成图片失败: {result.get('errmsg')}"}
        
    print(f"[{get_current_time()}] [INFO] 生成图片请求成功，开始获取history_record_id")
    return {"status": "success", "data": result.get("data", {})}

def get_history_by_ids(refresh_token, history_record_ids, max_retries=30, retry_interval=2):
    uri = "/mweb/v1/get_history_by_ids"
    headers, params = get_common_params(refresh_token, uri)
    
    # 移除Accept-Encoding头
    headers.pop('Accept-Encoding', None)
    
    print(f"[{get_current_time()}] [INFO] 开始获取历史记录: POST {uri}")
    print(f"[{get_current_time()}] [INFO] 历史记录ID: {history_record_ids}")
    
    data = {
        "history_ids": history_record_ids,
        "image_info": {
            "width": 2048,
            "height": 2048,
            "format": "webp",
            "image_scene_list": [
                {
                    "scene": "normal",
                    "width": 2400,
                    "height": 2400,
                    "uniq_key": "2400",
                    "format": "webp",
                }
            ]
        },
        "http_common_info": {
            "aid": int(DEFAULT_ASSISTANT_ID)
        }
    }
    
    for attempt in range(max_retries):
        print(f"[{get_current_time()}] [INFO] 尝试获取历史记录，第 {attempt+1}/{max_retries} 次")
        
        response = requests.post(
            f"https://jimeng.jianying.com{uri}",
            headers=headers,
            params=params,
            json=data
        )
        
        if response.status_code != 200:
            print(f"[{get_current_time()}] [ERROR] 获取历史记录失败: 状态码 {response.status_code}, 响应: {response.text}")
            if attempt == max_retries - 1:
                raise Exception(f"获取图片结果失败: {response.status_code}")
            print(f"[{get_current_time()}] [INFO] 等待 {retry_interval} 秒后重试")
            time.sleep(retry_interval)
            continue
            
        result = response.json()
        print(f"[{get_current_time()}] [INFO] 历史记录响应: {json.dumps(result, ensure_ascii=False)}")
        
        if result.get("ret") != "0":
            print(f"[{get_current_time()}] [ERROR] 获取历史记录失败: {result.get('errmsg')}")
            if attempt == max_retries - 1:
                raise Exception(f"获取图片结果失败: {result.get('errmsg')}")
            print(f"[{get_current_time()}] [INFO] 等待 {retry_interval} 秒后重试")
            time.sleep(retry_interval)
            continue
        
        # 检查结果状态
        history_id = history_record_ids[0]
        if not result.get("data", {}).get(history_id):
            print(f"[{get_current_time()}] [ERROR] 记录不存在: {history_id}")
            if attempt == max_retries - 1:
                raise Exception("记录不存在")
            print(f"[{get_current_time()}] [INFO] 等待 {retry_interval} 秒后重试")
            time.sleep(retry_interval)
            continue
            
        history_data = result["data"][history_id]
        status = history_data.get("status")
        fail_code = history_data.get("fail_code")
        
        if status == 50:  # 完成
            print(f"[{get_current_time()}] [INFO] 图片生成完成，状态码: {status}")
            return result
        elif status == 30:  # 失败
            if fail_code == '2038':
                print(f"[{get_current_time()}] [ERROR] 图片生成失败: 内容被过滤，状态码: {status}, 失败码: {fail_code}")
                raise Exception("内容被过滤")
            else:
                print(f"[{get_current_time()}] [ERROR] 图片生成失败: 状态码: {status}, 失败码: {fail_code}")
                raise Exception("图片生成失败")
        elif status == 20:  # 生成中
            print(f"[{get_current_time()}] [INFO] 图片生成中，状态码: {status}")
            if attempt < max_retries - 1:
                print(f"[{get_current_time()}] [INFO] 等待 {retry_interval} 秒后重试")
                time.sleep(retry_interval)
            else:
                print(f"[{get_current_time()}] [ERROR] 图片生成超时")
                raise Exception("图片生成超时")
        else:
            print(f"[{get_current_time()}] [WARNING] 未知的图片生成状态: {status}")
            if attempt == max_retries - 1:
                raise Exception(f"未知的图片生成状态: {status}")
            print(f"[{get_current_time()}] [INFO] 等待 {retry_interval} 秒后重试")
            time.sleep(retry_interval)

def main(prompt: str, refresh_token: str, width: int = 1664, height: int = 936, sample_strength: float = 0.5) -> Dict:
    """
    极梦AI图像生成接口
    
    Args:
        prompt: 提示词
        refresh_token: 刷新令牌
        width: 图像宽度
        height: 图像高度
        sample_strength: 采样强度
    
    Returns:
        Dict: 包含生成图像URL列表的字典
    """
    print(f"[{get_current_time()}] [INFO] {'=' * 50}")
    print(f"[{get_current_time()}] [INFO] 开始生成图片任务")
    print(f"[{get_current_time()}] [INFO] 提示词: {prompt}")
    print(f"[{get_current_time()}] [INFO] 参数: 宽度={width}, 高度={height}, 采样强度={sample_strength}")
    try:
        # 设置随机种子
        seed = int(time.time() * 1000) % 2147483647
        print(f"[{get_current_time()}] [INFO] 随机种子: {seed}")
        
        # 调用生成图片接口
        print(f"[{get_current_time()}] [INFO] 调用generate_images接口")
        generate_result = generate_images(prompt, refresh_token, sample_strength, width, height, seed)
        if generate_result.get("status") != "success":
            error_msg = generate_result.get("message", "生成图片失败")
            print(f"[{get_current_time()}] [ERROR] 生成图片接口调用失败: {error_msg}")
            return {
                "status": "error",
                "message": error_msg
            }
            
        # 获取history_record_id
        history_record_id = generate_result.get("data", {}).get("aigc_data", {}).get("history_record_id")
        if not history_record_id:
            print(f"[{get_current_time()}] [ERROR] 未获取到history_record_id")
            return {
                "status": "error",
                "message": "未获取到history_record_id"
            }
            
        print(f"[{get_current_time()}] [INFO] 获取到history_record_id: {history_record_id}")
            
        # 获取图片结果
        print(f"[{get_current_time()}] [INFO] 调用get_history_by_ids接口获取图片结果")
        result = get_history_by_ids(refresh_token, [history_record_id])
        
        # 提取图片URL列表
        print(f"[{get_current_time()}] [INFO] 开始提取图片URL")
        image_urls = []
        if result.get("data", {}).get(history_record_id):
            item_list = result["data"][history_record_id].get("item_list", [])
            print(f"[{get_current_time()}] [INFO] 获取到 {len(item_list)} 个图片项")
            
            for i, item in enumerate(item_list):
                image_url = None
                # 判断是否存在large_images及其image_url
                if (item.get("image") and 
                    item["image"].get("large_images") and 
                    len(item["image"]["large_images"]) > 0 and 
                    item["image"]["large_images"][0].get("image_url")):
                    image_url = item["image"]["large_images"][0]["image_url"]
                    print(f"[{get_current_time()}] [INFO] 从large_images中提取图片 #{i+1}: {image_url}")
                elif item.get("common_attr") and item["common_attr"].get("cover_url"):
                    image_url = item["common_attr"]["cover_url"]
                    print(f"[{get_current_time()}] [INFO] 从common_attr中提取图片 #{i+1}: {image_url}")
                
                if image_url:
                    image_urls.append(image_url)
        
        if not image_urls:
            print(f"[{get_current_time()}] [ERROR] 未能获取有效的图片URL")
            return {
                "status": "error",
                "message": "未能获取有效的图片URL"
            }
            
        print(f"[{get_current_time()}] [INFO] 成功提取 {len(image_urls)} 个图片URL")
            
        # 生成HTML图片标签列表
        print(f"[{get_current_time()}] [INFO] 生成HTML图片标签")
        image_html = ""
        for i, url in enumerate(image_urls):
            image_html += f'<img src="{url}">\n'
            print(f"[{get_current_time()}] [INFO] 生成图片 #{i+1} HTML标签: <img src=\"{url}\">")

        print(f"[{get_current_time()}] [INFO] 图片生成任务完成")
        print(f"[{get_current_time()}] [INFO] {'=' * 50}")
            
        return {
            "status": "success",
            "image_html": image_html
        }
    except Exception as e:
        import traceback
        print(f"[{get_current_time()}] [ERROR] 图片生成过程中发生错误: {str(e)}")
        print(f"[{get_current_time()}] [ERROR] 错误详情: {traceback.format_exc()}")
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    # 测试函数
    print(f"[{get_current_time()}] [INFO] 开始测试main函数")
    result = main(
        prompt="小鸭子在河里游泳，小猫在旁边吃鱼",
        refresh_token="f49656b2cc345895a880ba2c026c80ff"
    )
    print(f"[{get_current_time()}] [INFO] main函数返回结果: {json.dumps(result, ensure_ascii=False, indent=2)}") 