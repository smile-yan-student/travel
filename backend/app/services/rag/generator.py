"""
RAG内容生成器（Generator）。

基于检索结果，调用本地LLM生成景点讲解和知识问答。

功能特性：
- AI景点完整讲解（历史/建筑/文化/典故/游玩重点/避坑提示）
- 多轮知识问答（基于检索结果的精准回答）
- 行程人文短句（从知识库提取，不经过LLM，确定性）
- 点位卡片人文信息（从知识库结构化提取，不经过LLM）
- 知识库无数据时诚实降级
- 全局单例

支持的讲解风格：
- default: 默认风格
- history_focus: 历史文化重点
- photography_focus: 摄影重点
- family_friendly: 亲子友好

使用方式：
    from app.services.rag.generator import get_rag_generator

    # 获取全局RAG生成器单例
    generator = get_rag_generator()

    # 检查是否可用
    if generator.available:
        # 生成AI景点完整讲解
        explanation = await generator.generate_poi_explanation(
            "故宫",
            style="history_focus"
        )

        # 生成知识问答回答
        answer = await generator.generate_qa_answer(
            "故宫",
            "故宫的开放时间是什么？"
        )

        # 生成行程人文短句（不经过LLM，确定性）
        sentence = generator.generate_humanities_short_sentence("故宫")

        # 获取点位卡片人文信息（不经过LLM）
        card_info = generator.get_poi_card_info("故宫")
"""
import json
from typing import Any, Dict, List, Optional

from ... import ai as ai_mod
from .retriever import get_retriever


class RAGGenerator:
    """
    RAG内容生成器。

    基于检索结果 + 本地LLM生成高质量内容。
    """

    def __init__(self) -> None:
        """初始化RAG生成器。"""
        self.retriever = get_retriever()

    @property
    def available(self) -> bool:
        """
        生成器是否可用。

        Returns:
            bool: 是否可用（检索器和AI都可用）
        """
        return self.retriever.available and ai_mod.ai_available()

    async def generate_poi_explanation(
        self,
        poi_name: str,
        style: str = "default",
    ) -> Dict[str, Any]:
        """
        生成AI景点完整讲解。

        Args:
            poi_name: 景点名称
            style: 讲解风格（default/history_focus/photography_focus/family_friendly）

        Returns:
            Dict[str, Any]: 结构化讲解结果
        """
        # 1. 检索知识库
        knowledge = self.retriever.get_poi_knowledge(poi_name)
        context = self.retriever.get_context_for_generation(
            poi_name, max_tokens=3000
        )

        # 2. 如果知识库没有数据，诚实降级
        if not knowledge or not context:
            return {
                "poi_name": poi_name,
                "rag_retrieved": False,
                "message": f"暂无「{poi_name}」的详细知识库，以下为通用介绍",
                "introduction": f"{poi_name}是一处值得游览的景点。",
                "note": "AI生成内容，仅供参考，建议查阅官方资料获取准确信息",
            }

        # 3. 构建Prompt，基于检索结果生成讲解
        system_prompt = f"""你是一位专业的旅行文化讲解员。请基于以下知识库内容，为「{poi_name}」生成一份结构化的景点讲解。

要求：
1. 严格基于提供的知识库内容，不要编造知识库中没有的信息
2. 如果某个部分知识库中没有相关内容，标注"暂无详细资料"
3. 语言生动但准确，适合普通游客理解
4. 每个部分控制在合理长度，不要冗长

讲解风格：{style}

知识库内容：
{context}
"""

        user_prompt = f"""请为「{poi_name}」生成完整讲解，包含以下部分：
1. 一句话定位（30字以内）
2. 历史沿革（200-300字）
3. 建筑格局（150-200字）
4. 文化意义（150-200字）
5. 名人典故（3-5个，每个1-2句话）
6. 游玩重点（必看景点+推荐路线）
7. 拍照机位（2-3个）
8. 避坑提示（3-5条实用建议）

请用JSON格式输出，key为：introduction, history, architecture, culture, legends, visit_highlights, photo_spots, avoid_tips"""

        try:
            # 调用本地LLM生成
            response = await ai_mod.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )

            # 解析JSON响应
            try:
                # 尝试提取JSON
                content = response
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(content[json_start:json_end])
                else:
                    result = {"introduction": content}
            except Exception:
                result = {"introduction": response}

            # 字段规范化：确保各字段格式符合前端期望
            # visit_highlights可能是字典（必看景点+推荐路线），转换为字符串
            vh = result.get("visit_highlights")
            if isinstance(vh, dict):
                parts = []
                if "必看景点" in vh and isinstance(vh["必看景点"], list):
                    parts.append("必看景点：" + "、".join(vh["必看景点"][:5]))
                if "推荐路线" in vh:
                    parts.append("推荐路线：" + str(vh["推荐路线"]))
                result["visit_highlights"] = "\n".join(parts) if parts else str(vh)
            elif vh is not None and not isinstance(vh, str):
                result["visit_highlights"] = str(vh)

            # 确保legends/photo_spots/avoid_tips是字符串列表
            for list_field in ["legends", "photo_spots", "avoid_tips"]:
                val = result.get(list_field)
                if val is None:
                    result[list_field] = []
                elif isinstance(val, str):
                    result[list_field] = [val]
                elif isinstance(val, list):
                    result[list_field] = [str(item) for item in val]
                else:
                    result[list_field] = [str(val)]

            # 确保文本字段是字符串
            for text_field in ["introduction", "history", "architecture", "culture"]:
                val = result.get(text_field)
                if val is not None and not isinstance(val, str):
                    result[text_field] = str(val)

            result["poi_name"] = poi_name
            result["rag_retrieved"] = True
            result["sources"] = list(
                set(
                    [
                        doc.get("metadata", {}).get("source", "知识库")
                        for docs in knowledge.values()
                        for doc in docs
                    ]
                )
            )
            result["knowledge_chunks"] = sum(
                len(docs) for docs in knowledge.values()
            )
            return result

        except Exception as e:
            return {
                "poi_name": poi_name,
                "rag_retrieved": True,
                "error": f"生成失败: {str(e)}",
                "introduction": f"{poi_name}的详细讲解生成中，请稍后重试。",
            }

    async def generate_qa_answer(
        self,
        poi_name: str,
        question: str,
    ) -> Dict[str, Any]:
        """
        生成知识问答回答。

        Args:
            poi_name: 景点名称
            question: 用户问题

        Returns:
            Dict[str, Any]: 回答结果
        """
        # 1. 检索相关知识
        docs = self.retriever.search_by_query(
            question, poi_name=poi_name, n_results=5
        )

        if not docs:
            return {
                "answer": f"关于「{poi_name}」的这个问题，知识库中暂无详细资料。建议查阅官方资料或咨询景区工作人员。",
                "rag_retrieved": False,
                "sources": [],
            }

        # 2. 构建上下文
        context = "\n\n".join(
            [
                f"【资料{i+1}】{doc.get('document', '')}"
                for i, doc in enumerate(docs)
            ]
        )

        # 3. 构建Prompt
        system_prompt = f"""你是一位专业的旅行文化顾问。请基于以下知识库内容，回答用户关于「{poi_name}」的问题。

要求：
1. 严格基于提供的知识库内容回答，不要编造
2. 如果知识库中没有相关内容，诚实告知"知识库中暂无相关资料"
3. 回答简洁准确，适合游客快速了解
4. 可以引用知识库中的具体内容

知识库内容：
{context}
"""

        try:
            response = await ai_mod.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            return {
                "answer": response,
                "rag_retrieved": True,
                "sources": list(
                    set(
                        [
                            doc.get("metadata", {}).get("source", "知识库")
                            for doc in docs
                        ]
                    )
                ),
                "related_chunks": [
                    {
                        "chunk_type": doc.get("metadata", {}).get("chunk_type", ""),
                        "content": doc.get("document", "")[:200],
                        "relevance": doc.get("score", 0),
                    }
                    for doc in docs[:3]
                ],
            }

        except Exception as e:
            return {
                "answer": f"回答生成失败: {str(e)}",
                "rag_retrieved": True,
                "sources": [],
            }

    def generate_humanities_short_sentence(
        self,
        poi_name: str,
    ) -> str:
        """
        生成行程人文短句（从知识库提取，不经过LLM，确定性）。

        Args:
            poi_name: 景点名称

        Returns:
            str: 人文短句（50字以内）
        """
        # 从知识库提取summary或culture部分
        knowledge = self.retriever.get_poi_knowledge(poi_name)

        # 优先用summary
        if "summary" in knowledge and knowledge["summary"]:
            content = knowledge["summary"][0].get("document", "")
            if content:
                # 截取前50字
                return content[:50] + ("..." if len(content) > 50 else "")

        # 其次用culture
        if "culture" in knowledge and knowledge["culture"]:
            content = knowledge["culture"][0].get("document", "")
            if content:
                return content[:50] + ("..." if len(content) > 50 else "")

        # 最后用history
        if "history" in knowledge and knowledge["history"]:
            content = knowledge["history"][0].get("document", "")
            if content:
                return content[:50] + ("..." if len(content) > 50 else "")

        return ""

    def get_poi_card_info(
        self,
        poi_name: str,
    ) -> Dict[str, Any]:
        """
        获取点位卡片人文信息（从知识库结构化提取，不经过LLM）。

        Args:
            poi_name: 景点名称

        Returns:
            Dict[str, Any]: 点位卡片信息字典
        """
        knowledge = self.retriever.get_poi_knowledge(poi_name)

        def get_first_content(chunk_type: str, max_len: int = 100) -> str:
            """
            获取指定分块类型的第一条内容。

            Args:
                chunk_type: 分块类型
                max_len: 最大长度

            Returns:
                str: 内容（截取到max_len）
            """
            if chunk_type in knowledge and knowledge[chunk_type]:
                content = knowledge[chunk_type][0].get("document", "")
                return content[:max_len] + ("..." if len(content) > max_len else "")
            return ""

        return {
            "summary": get_first_content("summary", 80),
            "historical_origin": get_first_content("history", 100),
            "famous_legend": get_first_content("culture", 80),
            "best_time": get_first_content("visit_guide", 50),
            "avoid_tips": [
                doc.get("document", "")[:80]
                for doc in knowledge.get("visit_guide", [])[:3]
            ],
            "rag_available": bool(knowledge),
        }


# 全局单例
_generator: Optional[RAGGenerator] = None


def get_rag_generator() -> RAGGenerator:
    """
    获取全局RAG生成器单例。

    Returns:
        RAGGenerator: 全局RAG生成器单例
    """
    global _generator
    if _generator is None:
        _generator = RAGGenerator()
    return _generator
