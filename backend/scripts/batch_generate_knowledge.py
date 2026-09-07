#!/usr/bin/env python3
"""
批量生成景点知识库数据脚本

使用AI批量生成热门旅游城市的景点知识库数据，
数据结构与现有数据保持一致。

使用方法：
    python scripts/batch_generate_knowledge.py --city 成都 --count 5
    python scripts/batch_generate_knowledge.py --cities 成都,重庆,厦门 --count 3
"""
import os
import sys
import json
import argparse
import time
from typing import List, Dict, Any

import httpx

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.services.major_attractions import MajorAttractionsService


def call_ollama_chat(prompt: str, temperature: float = 0.7, max_tokens: int = 2000) -> str:
    """
    直接调用Ollama API进行对话

    Args:
        prompt: 提示词
        temperature: 温度
        max_tokens: 最大token数

    Returns:
        AI回复内容
    """
    model = settings.ollama_model or "qwen2:7b"

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                print(f"  ❌ Ollama API错误: {response.status_code} - {response.text}")
                return ""
    except Exception as e:
        print(f"  ❌ 调用Ollama失败: {e}")
        return ""


def generate_knowledge_for_attraction(attraction: Dict[str, Any]) -> Dict[str, Any]:
    """
    为单个景点生成知识库数据

    Args:
        attraction: 景点信息

    Returns:
        知识库数据
    """
    name = attraction.get("name", "")
    city = attraction.get("city", "")
    level = attraction.get("level", "")

    # 构造Prompt
    prompt = f"""请为景点「{name}」（位于{city}，等级：{level or '未知'}）生成详细的知识库数据。

要求：
1. 数据结构必须包含以下字段：
   - name: 景点名称
   - alias: 别名列表（数组）
   - city: 城市
   - district: 区县
   - category: 分类（景点/美食/购物/夜生活）
   - level: 景区等级（5A/4A/3A/无）
   - description: 景点描述（100-200字）
   - recommended_duration: 推荐游览时长（分钟，整数）
   - inner_route: 内部路线（数组，每个包含name, description, duration_min, order, highlight, photo_spot）
   - nearby_attractions: 附近景点（数组，每个包含name, category, description, distance_m, recommended_slot, duration_min）
   - best_time: 最佳游览时间（字符串）
   - avoid_tips: 避坑提示（数组，每个是字符串）

2. 内部路线至少3个，最多8个，按游览顺序排列
3. 附近景点至少2个，最多5个，距离在500米-3公里之间
4. 避坑提示至少3条
5. 数据要真实、准确、实用
6. 只返回JSON数据，不要返回其他内容

请生成JSON数据："""

    try:
        # 调用AI生成
        content = call_ollama_chat(prompt, temperature=0.7, max_tokens=2000)

        if not content:
            print(f"  ❌ AI返回为空")
            return None

        # 尝试提取JSON
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            knowledge_data = json.loads(json_str)
            return knowledge_data
        else:
            print(f"  ❌ 无法解析JSON响应: {content[:200]}")
            return None

    except Exception as e:
        print(f"  ❌ 生成失败: {e}")
        return None


def save_knowledge_data(knowledge_data: Dict[str, Any], output_dir: str):
    """
    保存知识库数据到文件

    Args:
        knowledge_data: 知识库数据
        output_dir: 输出目录
    """
    name = knowledge_data.get("name", "unknown")
    # 清理文件名
    safe_name = "".join(c for c in name if c.isalnum() or c in "._- ")
    filename = f"{safe_name}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(knowledge_data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 已保存: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="批量生成景点知识库数据")
    parser.add_argument("--city", type=str, help="单个城市")
    parser.add_argument("--cities", type=str, help="多个城市，逗号分隔")
    parser.add_argument("--count", type=int, default=3, help="每个城市生成的景点数量")
    parser.add_argument("--output", type=str, default="app/data/knowledge_base/processed", help="输出目录")
    parser.add_argument("--delay", type=float, default=2.0, help="每次生成之间的延迟（秒）")

    args = parser.parse_args()

    # 确定城市列表
    if args.city:
        cities = [args.city]
    elif args.cities:
        cities = [c.strip() for c in args.cities.split(",")]
    else:
        # 默认热门旅游城市
        cities = ["成都", "重庆", "厦门", "丽江", "西安", "苏州", "南京", "青岛"]

    print(f"🚀 开始批量生成景点知识库数据")
    print(f"📋 城市列表: {', '.join(cities)}")
    print(f"📊 每个城市生成: {args.count} 个景点")
    print(f"📁 输出目录: {args.output}")
    print()

    # 确保输出目录存在
    os.makedirs(args.output, exist_ok=True)

    # 初始化服务
    major_attractions_service = MajorAttractionsService()

    total_generated = 0
    total_failed = 0

    for city in cities:
        print(f"📍 正在处理城市: {city}")

        # 获取该城市的主要景点
        attractions = major_attractions_service.get_major_attractions_by_city(city)

        if not attractions:
            print(f"  ⚠️  该城市没有主要景点数据，跳过")
            print()
            continue

        # 限制数量
        attractions = attractions[:args.count]
        print(f"  📋 找到 {len(attractions)} 个景点")

        for i, attraction in enumerate(attractions, 1):
            name = attraction.get("name", "")
            print(f"  [{i}/{len(attractions)}] 正在生成: {name}")

            # 生成知识库数据
            knowledge_data = generate_knowledge_for_attraction(attraction)

            if knowledge_data:
                # 保存
                save_knowledge_data(knowledge_data, args.output)
                total_generated += 1
            else:
                total_failed += 1

            # 延迟
            if i < len(attractions):
                time.sleep(args.delay)

        print()

    print(f"✅ 批量生成完成！")
    print(f"📊 总计: 成功 {total_generated} 个，失败 {total_failed} 个")


if __name__ == "__main__":
    main()
