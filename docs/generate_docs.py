#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成项目资料体系5份Word文档
1. 产品需求文档（PRD）
2. 运营方案
3. 商业计划书
4. 竞品分析报告
5. 用户旅程地图
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
import os

OUTPUT_DIR = "/Users/passenger/Desktop/travel/docs/项目资料体系"

def set_chinese_font(run, font_name='微软雅黑', size=11, bold=False, color=None):
    """设置中文字体"""
    run.font.name = font_name
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color
    r = run._element
    r.rPr.rFonts.set(qn('w:eastAsia'), font_name)

def add_title(doc, text, level=1):
    """添加标题"""
    if level == 0:
        p = doc.add_heading('', level=0)
        run = p.runs[0] if p.runs else p.add_run()
        run.text = text
        set_chinese_font(run, size=22, bold=True, color=RGBColor(0x1a, 0x1a, 0x2e))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif level == 1:
        p = doc.add_heading('', level=1)
        run = p.runs[0] if p.runs else p.add_run()
        run.text = text
        set_chinese_font(run, size=18, bold=True, color=RGBColor(0x2c, 0x3e, 0x50))
    elif level == 2:
        p = doc.add_heading('', level=2)
        run = p.runs[0] if p.runs else p.add_run()
        run.text = text
        set_chinese_font(run, size=15, bold=True, color=RGBColor(0x34, 0x49, 0x5e))
    elif level == 3:
        p = doc.add_heading('', level=3)
        run = p.runs[0] if p.runs else p.add_run()
        run.text = text
        set_chinese_font(run, size=13, bold=True, color=RGBColor(0x4a, 0x5f, 0x7a))
    return p

def add_para(doc, text, size=11, bold=False, indent=True):
    """添加段落"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_chinese_font(run, size=size, bold=bold)
    if indent:
        p.paragraph_format.first_line_indent = Pt(22)
    p.paragraph_format.line_spacing = 1.5
    return p

def add_bullet(doc, text, level=0):
    """添加项目符号"""
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    set_chinese_font(run, size=11)
    p.paragraph_format.left_indent = Pt(22 + level * 22)
    return p

def add_table(doc, headers, rows, col_widths=None):
    """添加表格"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Light Grid Accent 1'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # 表头
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        run = p.add_run(header)
        set_chinese_font(run, size=10, bold=True, color=RGBColor(0xff, 0xff, 0xff))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # 设置表头背景色
        shading = cell._element.get_or_add_tcPr()
        shading_elm = shading.makeelement(qn('w:shd'), {
            qn('w:fill'): '2C3E50',
            qn('w:val'): 'clear'
        })
        shading.append(shading_elm)
    
    # 数据行
    for row_idx, row_data in enumerate(rows):
        for col_idx, cell_data in enumerate(row_data):
            cell = table.rows[row_idx + 1].cells[col_idx]
            cell.text = ''
            p = cell.paragraphs[0]
            run = p.add_run(str(cell_data))
            set_chinese_font(run, size=10)
    
    # 设置列宽
    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)
    
    return table

def add_doc_info(doc, title, version, date, author, status):
    """添加文档信息表"""
    add_title(doc, '文档信息', level=2)
    add_table(doc, 
        ['项目', '内容'],
        [
            ['文档名称', title],
            ['版本', version],
            ['日期', date],
            ['状态', status],
            ['作者', author],
        ],
        col_widths=[2, 4.5]
    )
    doc.add_paragraph()

# ============================================================
# 1. 产品需求文档（PRD）
# ============================================================
def generate_prd():
    doc = Document()
    
    # 页面设置
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    
    add_title(doc, 'AI旅行规划产品需求文档（PRD）', level=0)
    doc.add_paragraph()
    
    add_doc_info(doc, 'AI旅行规划产品需求文档', 'v1.0', '2026-09-03', '产品团队', '待评审')
    
    # 一、产品概述
    add_title(doc, '一、产品概述', level=1)
    
    add_title(doc, '1.1 产品定位', level=2)
    add_para(doc, 'AI旅行规划产品是一款基于大语言模型（LLM）和检索增强生成（RAG）技术的智能旅行规划工具。产品通过自然语言对话的方式，帮助用户快速生成个性化的旅行行程，提供景点推荐、路线规划、预算估算、预约提醒、避坑提示等全方位的旅行规划服务。')
    
    add_title(doc, '1.2 产品愿景', level=2)
    add_para(doc, '让每个人都能轻松规划完美的旅行，激发人们走出去、探索世界的勇气。')
    
    add_title(doc, '1.3 产品目标', level=2)
    add_bullet(doc, '降低旅行规划门槛，用户通过自然语言对话即可生成完整行程')
    add_bullet(doc, '提升规划质量，基于知识库和规则引擎生成合理、实用的行程')
    add_bullet(doc, '个性化推荐，根据用户偏好、人群、预算等生成定制化行程')
    add_bullet(doc, '信息透明，提供预约提醒、避坑提示、人文介绍等增值信息')
    
    add_title(doc, '1.4 目标用户', level=2)
    add_table(doc,
        ['用户类型', '特征', '核心需求', '占比预估'],
        [
            ['休闲游客', '偶尔出行，追求轻松体验', '简单易用、经典路线、避坑提示', '40%'],
            ['深度玩家', '频繁出行，追求独特体验', '个性化、小众景点、深度攻略', '25%'],
            ['亲子家庭', '带孩子出行，关注安全舒适', '亲子景点、行程宽松、设施完善', '20%'],
            ['情侣/朋友', '结伴出行，追求浪漫有趣', '打卡景点、美食推荐、拍照胜地', '15%'],
        ],
        col_widths=[1.2, 2, 2.2, 1.1]
    )
    
    # 二、产品功能架构
    add_title(doc, '二、产品功能架构', level=1)
    
    add_title(doc, '2.1 整体架构', level=2)
    add_para(doc, '产品分为用户端和管理后台两大系统。用户端包含对话、规划、探索、我的四大模块；管理后台包含数据看板、知识库管理、审核管理、用户管理、系统设置五大模块。')
    
    add_title(doc, '2.2 用户端功能架构', level=2)
    add_table(doc,
        ['模块', '子模块', '功能说明', '优先级'],
        [
            ['对话模块', '智能对话', '自然语言对话，意图识别，多轮交互', 'P0'],
            ['', '行程生成', '基于对话内容生成完整行程', 'P0'],
            ['', '行程调整', '支持修改、优化已生成的行程', 'P0'],
            ['', '人文介绍', '景点、历史、名人相关人文知识介绍', 'P1'],
            ['规划模块', '行程详情', '时间轴展示每日行程', 'P0'],
            ['', '地图展示', '地图可视化行程路线和点位', 'P0'],
            ['', '预算估算', '行程总预算及明细', 'P0'],
            ['', '预约提醒', '需要预约的景点提醒', 'P0'],
            ['', '避坑提示', '旅行常见坑点提示', 'P1'],
            ['', '行程导出', '导出为图片/PDF/分享链接', 'P1'],
            ['探索模块', '地图探索', '地图查看周边景点', 'P1'],
            ['', '景点搜索', '搜索目的地景点', 'P1'],
            ['', '景点详情', '景点介绍、开放时间、票价', 'P1'],
            ['', '热门推荐', '热门目的地和景点推荐', 'P2'],
            ['我的模块', '个人信息', '用户资料管理', 'P0'],
            ['', '历史行程', '查看和管理历史行程', 'P0'],
            ['', '收藏夹', '收藏喜欢的景点和行程', 'P1'],
            ['', '设置', '偏好设置、通知设置', 'P1'],
            ['', '登录注册', '邮箱验证码登录注册', 'P0'],
        ],
        col_widths=[1, 1.2, 3.2, 0.8]
    )
    
    add_title(doc, '2.3 管理后台功能架构', level=2)
    add_table(doc,
        ['模块', '子模块', '功能说明', '优先级'],
        [
            ['数据看板', '核心指标', '用户数、行程数、调用量、成功率', 'P0'],
            ['', '趋势图表', '日活、留存、转化趋势', 'P1'],
            ['知识库管理', '景点库', '景点信息CRUD、批量导入导出', 'P0'],
            ['', '行程库', '经典行程管理', 'P1'],
            ['', '美食库', '美食推荐管理', 'P1'],
            ['', '住宿库', '住宿区域管理', 'P2'],
            ['', '避坑库', '避坑提示管理', 'P0'],
            ['', '人文库', '人文知识管理', 'P1'],
            ['审核管理', '待审核列表', '待审核数据列表', 'P0'],
            ['', '审核操作', '通过/拒绝/备注', 'P0'],
            ['', '审核统计', '审核量、通过率、审核人效率', 'P1'],
            ['用户管理', '用户列表', '用户信息查看', 'P0'],
            ['', '用户操作', '封禁/解封/角色管理', 'P0'],
            ['', '用户统计', '注册量、活跃度、留存', 'P1'],
            ['系统设置', 'API配置', 'LLM、地图、邮件等API配置', 'P0'],
            ['', '限流配置', '用户级/全局调用次数限制', 'P0'],
            ['', '系统参数', '规划参数、缓存参数等', 'P1'],
        ],
        col_widths=[1, 1.2, 3.2, 0.8]
    )
    
    # 三、功能需求详细说明
    add_title(doc, '三、功能需求详细说明', level=1)
    
    add_title(doc, '3.1 对话模块', level=2)
    
    add_title(doc, '3.1.1 智能对话', level=3)
    add_para(doc, '用户通过自然语言与AI助手对话，系统识别用户意图并给出相应回复。')
    add_bullet(doc, '输入方式：文本输入，支持中文自然语言')
    add_bullet(doc, '意图类型：行程规划、行程调整、信息咨询、人文介绍、其他')
    add_bullet(doc, '多轮对话：支持上下文理解，用户可逐步补充需求')
    add_bullet(doc, '流式输出：回复采用流式输出，提升用户体验')
    add_bullet(doc, '参数引导：当关键参数缺失时，主动引导用户补充')
    
    add_title(doc, '3.1.2 行程生成', level=3)
    add_para(doc, '当用户意图为行程规划且参数完整时，系统生成完整的旅行行程。')
    add_bullet(doc, '必填参数：目的地')
    add_bullet(doc, '可选参数：天数（默认2-3天）、人数（默认1人）、人群类型、预算、出行方式')
    add_bullet(doc, '生成内容：每日行程（景点、时间、交通、餐饮）、预算估算、预约提醒、避坑提示')
    add_bullet(doc, '生成时间：目标<4秒')
    
    add_title(doc, '3.1.3 行程调整', level=3)
    add_bullet(doc, '支持修改天数、人数、预算等参数后重新生成')
    add_bullet(doc, '支持增加/删除/替换景点')
    add_bullet(doc, '支持调整景点顺序和时间')
    add_bullet(doc, '调整后保持行程合理性（时间、距离、逻辑）')
    
    add_title(doc, '3.2 规划模块', level=2)
    
    add_title(doc, '3.2.1 行程详情', level=3)
    add_bullet(doc, '时间轴展示：按天展示，每天按时间顺序排列')
    add_bullet(doc, '景点卡片：包含景点名称、图片、介绍、开放时间、票价')
    add_bullet(doc, '交通信息：景点间交通方式和时长')
    add_bullet(doc, '餐饮推荐：午餐/晚餐推荐')
    add_bullet(doc, '住宿建议：住宿区域推荐（不推荐具体酒店）')
    
    add_title(doc, '3.2.2 地图展示', level=3)
    add_bullet(doc, '点位标注：所有景点在地图上标注')
    add_bullet(doc, '路线连线：按行程顺序连线，不同天不同颜色')
    add_bullet(doc, '交互联动：点击地图点位，联动显示景点卡片')
    add_bullet(doc, '缩放平移：支持地图缩放和平移')
    
    add_title(doc, '3.2.3 预约提醒', level=3)
    add_bullet(doc, '自动识别：行程中需要预约的景点自动标注')
    add_bullet(doc, '提醒内容：预约渠道、放票时间、限流数量、闭馆日')
    add_bullet(doc, '醒目展示：在行程详情页顶部展示预约提醒清单')
    
    add_title(doc, '3.3 探索模块', level=2)
    add_bullet(doc, '地图探索：以地图为核心，展示目的地周边景点')
    add_bullet(doc, '分类筛选：按景点类型（自然风光、历史古迹、主题乐园、博物馆、美食购物）筛选')
    add_bullet(doc, '景点详情：点击景点查看详细信息（介绍、开放时间、票价、用户评价）')
    add_bullet(doc, '加入行程：可将感兴趣的景点加入当前行程')
    
    add_title(doc, '3.4 我的模块', level=2)
    add_bullet(doc, '个人信息：头像、昵称、邮箱、旅行偏好')
    add_bullet(doc, '历史行程：按时间线展示所有历史行程，支持查看、复制、删除')
    add_bullet(doc, '收藏夹：收藏的景点和行程，支持分类管理')
    add_bullet(doc, '登录注册：邮箱验证码方式登录注册')
    add_bullet(doc, '设置：通知设置、隐私设置、清除缓存')
    
    # 四、非功能需求
    add_title(doc, '四、非功能需求', level=1)
    
    add_title(doc, '4.1 性能需求', level=2)
    add_table(doc,
        ['指标', '目标值', '说明'],
        [
            ['API响应时间', '<500ms（P95）', '普通API接口'],
            ['行程生成时间', '<4s（P95）', '包含RAG检索+LLM生成'],
            ['对话首Token延迟', '<2s', '流式输出首Token'],
            ['检索时间', '<200ms', '向量检索+重排序'],
            ['并发用户数', '100+', '同时在线用户'],
            ['系统可用性', '>99.5%', '月度可用性'],
        ],
        col_widths=[1.5, 1.5, 3.5]
    )
    
    add_title(doc, '4.2 安全需求', level=2)
    add_bullet(doc, '用户认证：JWT Token认证，Access Token 2小时，Refresh Token 7天')
    add_bullet(doc, '密码安全：bcrypt加密存储，cost factor=12')
    add_bullet(doc, '数据隔离：用户只能访问自己的数据')
    add_bullet(doc, '接口限流：用户级和全局级调用次数限制')
    add_bullet(doc, '输入校验：所有输入参数校验，防止SQL注入、XSS')
    add_bullet(doc, '敏感数据：手机号、邮箱等敏感信息脱敏展示')
    
    add_title(doc, '4.3 兼容性需求', level=2)
    add_bullet(doc, '浏览器：Chrome 90+、Firefox 88+、Safari 14+、Edge 90+')
    add_bullet(doc, '设备：PC端、平板端、手机端响应式适配')
    add_bullet(doc, '网络：支持3G/4G/5G/WiFi，弱网环境有降级处理')
    
    add_title(doc, '4.4 可扩展性需求', level=2)
    add_bullet(doc, '模块化设计：各功能模块独立，可单独扩展')
    add_bullet(doc, '微服务架构：后端按业务领域拆分，支持水平扩展')
    add_bullet(doc, '插件化：知识库、LLM模型、地图服务可插拔替换')
    
    # 五、验收标准
    add_title(doc, '五、验收标准', level=1)
    
    add_table(doc,
        ['验收项', '验收标准', '优先级'],
        [
            ['对话功能', '用户可通过自然语言对话，系统正确识别意图并回复', 'P0'],
            ['行程生成', '输入目的地和天数，可生成包含景点、时间、交通的完整行程', 'P0'],
            ['行程展示', '行程详情页正确展示时间轴、地图、预算、预约提醒', 'P0'],
            ['用户系统', '用户可注册、登录、查看个人信息和历史行程', 'P0'],
            ['管理后台', '管理员可管理知识库、审核数据、查看数据看板', 'P0'],
            ['性能达标', 'API响应<500ms，行程生成<4s，并发100+稳定', 'P1'],
            ['安全达标', '无高危安全漏洞，数据隔离正确，限流生效', 'P1'],
            ['RAG效果', '检索准确率>85%，生成内容基于知识库，无明显幻觉', 'P1'],
        ],
        col_widths=[1.2, 3.8, 0.8]
    )
    
    # 六、附录
    add_title(doc, '六、附录', level=1)
    
    add_title(doc, '6.1 术语表', level=2)
    add_table(doc,
        ['术语', '说明'],
        [
            ['LLM', '大语言模型（Large Language Model）'],
            ['RAG', '检索增强生成（Retrieval-Augmented Generation）'],
            ['POI', '兴趣点（Point of Interest），指景点、餐厅等地点'],
            ['主POI', '大型景区，包含多个子景点'],
            ['子POI', '主POI内的具体景点'],
            ['JWT', 'JSON Web Token，用于用户认证'],
            ['PRD', '产品需求文档（Product Requirements Document）'],
        ],
        col_widths=[1.5, 5]
    )
    
    add_title(doc, '6.2 参考文档', level=2)
    add_bullet(doc, '《AI旅行规划产品设计规划文档》')
    add_bullet(doc, '《RAG知识库增强技术实现方案文档》')
    add_bullet(doc, '《行程规划引擎规则体系设计》')
    
    output_path = os.path.join(OUTPUT_DIR, '01_产品需求文档（PRD）.docx')
    doc.save(output_path)
    print(f'已生成: {output_path}')
    return output_path


# ============================================================
# 2. 运营方案
# ============================================================
def generate_operation_plan():
    doc = Document()
    
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    
    add_title(doc, 'AI旅行规划产品运营方案', level=0)
    doc.add_paragraph()
    
    add_doc_info(doc, 'AI旅行规划产品运营方案', 'v1.0', '2026-09-03', '运营团队', '待评审')
    
    # 一、运营目标
    add_title(doc, '一、运营目标', level=1)
    
    add_title(doc, '1.1 总体目标', level=2)
    add_para(doc, '通过系统化的运营策略，在产品上线后6个月内实现10万注册用户，日活跃用户达到5000+，行程生成量达到10万+，建立良好的用户口碑和品牌影响力。')
    
    add_title(doc, '1.2 分阶段目标', level=2)
    add_table(doc,
        ['阶段', '时间', '注册用户', '日活', '行程生成量', '核心任务'],
        [
            ['冷启动期', '第1-2月', '5,000', '500', '5,000', '种子用户获取、产品验证'],
            ['成长期', '第3-4月', '30,000', '2,000', '40,000', '用户增长、内容建设'],
            ['爆发期', '第5-6月', '100,000', '5,000', '100,000', '品牌传播、商业化探索'],
        ],
        col_widths=[1, 1, 1, 0.8, 1.2, 1.5]
    )
    
    # 二、用户运营
    add_title(doc, '二、用户运营', level=1)
    
    add_title(doc, '2.1 冷启动策略', level=2)
    
    add_title(doc, '2.1.1 种子用户获取', level=3)
    add_bullet(doc, '邀请制：邀请旅行达人、博主、KOL作为首批种子用户')
    add_bullet(doc, '社群运营：建立微信/QQ用户群，收集反馈，快速迭代')
    add_bullet(doc, '内测活动：限量内测资格，参与内测送会员/积分奖励')
    add_bullet(doc, '口碑传播：种子用户分享行程生成结果，带来自然增长')
    
    add_title(doc, '2.1.2 种子用户画像', level=3)
    add_table(doc,
        ['用户类型', '获取渠道', '数量目标', '核心价值'],
        [
            ['旅行达人', '小红书/抖音/马蜂窝私信邀请', '100人', '内容贡献、口碑传播'],
            ['旅行博主', '博主合作、邮件邀约', '50人', '专业反馈、内容生产'],
            ['普通用户', '社群、朋友圈、论坛', '500人', '真实使用反馈'],
            ['行业专家', '行业会议、人脉推荐', '20人', '战略建议、资源对接'],
        ],
        col_widths=[1.2, 2.2, 1, 2.1]
    )
    
    add_title(doc, '2.2 用户增长策略', level=2)
    
    add_title(doc, '2.2.1 内容营销', level=3)
    add_bullet(doc, '小红书：发布旅行攻略、行程分享、避坑指南，植入产品')
    add_bullet(doc, '抖音/视频号：制作行程生成过程短视频、旅行Vlog')
    add_bullet(doc, '微信公众号：深度旅行攻略、产品使用教程、行业洞察')
    add_bullet(doc, '知乎：回答旅行相关问题，提供专业建议，引流产品')
    add_bullet(doc, '马蜂窝/携程：发布攻略游记，在评论区推荐产品')
    
    add_title(doc, '2.2.2 KOL合作', level=3)
    add_bullet(doc, '头部KOL（10万+粉丝）：品牌合作、产品测评、定制行程')
    add_bullet(doc, '腰部KOL（1万-10万粉丝）：产品体验、行程分享、抽奖活动')
    add_bullet(doc, '尾部KOC（1000-1万粉丝）：真实体验、口碑传播、社群推广')
    add_bullet(doc, '合作模式：免费体验+佣金分成、固定费用+效果分成、置换合作')
    
    add_title(doc, '2.2.3 裂变增长', level=3)
    add_bullet(doc, '分享奖励：用户分享行程到社交平台，获得积分/会员天数')
    add_bullet(doc, '邀请奖励：邀请好友注册，双方都获得奖励')
    add_bullet(doc, '行程海报：生成精美的行程海报，便于用户分享传播')
    add_bullet(doc, '社群裂变：建立城市旅行社群，群内分享产品，群友专属优惠')
    
    add_title(doc, '2.3 留存活跃策略', level=2)
    
    add_title(doc, '2.3.1 新用户引导', level=3)
    add_bullet(doc, '新手任务：完成首次对话、生成首个行程、分享行程等任务，获得奖励')
    add_bullet(doc, '引导流程：首次使用时的功能引导，帮助用户快速上手')
    add_bullet(doc, '示例推荐：首页展示热门目的地和示例行程，降低使用门槛')
    add_bullet(doc, '7日留存计划：新用户注册后7天内，每天推送不同的旅行灵感')
    
    add_title(doc, '2.3.2 活跃激励', level=3)
    add_table(doc,
        ['激励方式', '具体内容', '目标'],
        [
            ['积分体系', '生成行程、分享、邀请好友获得积分，积分可兑换会员', '提升日活'],
            ['签到打卡', '每日签到获得积分，连续签到有额外奖励', '提升留存'],
            ['会员体系', '免费会员+付费会员，付费会员享受更多行程次数和高级功能', '提升付费转化'],
            ['成就系统', '生成X个行程、去过X个城市等成就徽章', '提升用户粘性'],
            ['等级体系', '用户等级随使用量提升，等级越高权益越多', '提升长期留存'],
        ],
        col_widths=[1.2, 3.5, 1.8]
    )
    
    add_title(doc, '2.3.3 召回策略', level=3)
    add_bullet(doc, '邮件召回：用户7天未登录，发送热门目的地推荐邮件')
    add_bullet(doc, '节日营销：节假日前后推送旅行灵感和优惠活动')
    add_bullet(doc, '个性化推荐：基于用户历史行程，推荐相似目的地和行程')
    add_bullet(doc, '流失调研：用户流失时发送调研问卷，了解原因，赠送回归奖励')
    
    add_title(doc, '2.4 用户分层运营', level=2)
    add_table(doc,
        ['用户层级', '定义', '运营策略', '核心指标'],
        [
            ['新用户', '注册7天内', '新手引导、首次体验激励', '7日留存率'],
            ['活跃用户', '每周使用≥3次', '高级功能推荐、社群运营', '周留存率'],
            ['核心用户', '每月生成行程≥5个', '专属客服、内测资格、内容共创', '月留存率'],
            ['付费用户', '购买会员/付费功能', '专属权益、优先体验、续费提醒', '续费率'],
            ['流失用户', '30天未登录', '召回邮件、回归奖励、流失调研', '召回率'],
        ],
        col_widths=[1, 1.5, 2.8, 1.2]
    )
    
    # 三、内容运营
    add_title(doc, '三、内容运营', level=1)
    
    add_title(doc, '3.1 知识库建设', level=2)
    
    add_title(doc, '3.1.1 内容来源', level=3)
    add_table(doc,
        ['来源', '内容类型', '质量等级', '获取方式', '占比'],
        [
            ['官方渠道', '景点介绍、开放时间、票价、预约规则', '⭐⭐⭐⭐⭐', '人工整理、官网爬取', '30%'],
            ['公开数据集', '景点基础信息、地理坐标', '⭐⭐⭐⭐', '数据采购、开源数据', '20%'],
            ['百科知识', '历史文化、名人故事、景点介绍', '⭐⭐⭐⭐', '维基/百度百科', '15%'],
            ['旅游平台', '攻略、游记、避坑提示', '⭐⭐⭐', '马蜂窝/携程，去广告处理', '20%'],
            ['AI生成', '基于已有知识扩展、行程模板', '⭐⭐⭐', 'LLM生成，人工审核', '10%'],
            ['用户贡献', '用户上传的行程、评价、提示', '⭐⭐', 'UGC，严格审核', '5%'],
        ],
        col_widths=[1, 2.2, 0.8, 1.8, 0.7]
    )
    
    add_title(doc, '3.1.2 内容建设节奏', level=3)
    add_bullet(doc, '第1月：覆盖Top 50热门城市，每个城市50+景点，共2500+景点')
    add_bullet(doc, '第2月：扩展到Top 100城市，补充美食、避坑、人文知识')
    add_bullet(doc, '第3月：覆盖Top 200城市，完善行程库、住宿库')
    add_bullet(doc, '第4-6月：持续优化内容质量，补充小众目的地，UGC内容上线')
    
    add_title(doc, '3.2 UGC激励', level=2)
    add_bullet(doc, '行程分享：用户分享自己的行程，通过审核后纳入行程库，获得积分奖励')
    add_bullet(doc, '景点纠错：用户发现景点信息错误，提交纠错，审核通过后获得奖励')
    add_bullet(doc, '避坑分享：用户分享旅行避坑经验，审核通过后纳入避坑库')
    add_bullet(doc, '内容创作者：优质内容创作者可获得认证、流量扶持、收益分成')
    
    add_title(doc, '3.3 内容审核', level=2)
    add_bullet(doc, '自动审核：敏感词检测、重复内容检测、格式校验')
    add_bullet(doc, '人工审核：所有新增内容必须人工审核通过后才能上线')
    add_bullet(doc, '审核标准：准确性、完整性、时效性、原创性、无广告')
    add_bullet(doc, '审核流程：提交→自动审核→人工审核→通过/拒绝→上线/修改')
    add_bullet(doc, '质量评分：每条内容都有质量评分，低分内容定期清理')
    
    # 四、活动运营
    add_title(doc, '四、活动运营', level=1)
    
    add_title(doc, '4.1 节日活动', level=2)
    add_table(doc,
        ['节日', '活动主题', '活动形式', '时间'],
        [
            ['春节', '回家路上的风景', '生成家乡行程，分享得红包', '春节前1周'],
            ['五一', '五一出行季', '热门目的地推荐，行程生成抽奖', '4月中下旬'],
            ['暑假', '暑期亲子游', '亲子行程专题，会员优惠', '7-8月'],
            ['国庆', '国庆黄金周', '国内热门目的地攻略，预约提醒', '9月中下旬'],
            ['双十一', '旅行规划节', '会员打折，行程生成免限额', '11月11日前后'],
            ['元旦', '新年旅行计划', '生成新年第一个行程，立Flag活动', '12月底-1月初'],
        ],
        col_widths=[0.8, 1.5, 2.5, 1.7]
    )
    
    add_title(doc, '4.2 主题活动', level=2)
    add_bullet(doc, '旅行达人赛：邀请用户生成优质行程，评选最佳行程，奖励会员/礼品')
    add_bullet(doc, '城市探索计划：每周推荐一个城市，生成该城市行程打卡')
    add_bullet(doc, '小众目的地发现：鼓励用户分享小众景点，发现新目的地')
    add_bullet(doc, '红色旅行专题：革命先辈相关地点推荐，人文历史介绍')
    
    # 五、数据分析
    add_title(doc, '五、数据分析', level=1)
    
    add_title(doc, '5.1 核心指标体系', level=2)
    add_table(doc,
        ['指标类别', '核心指标', '计算公式', '目标值'],
        [
            ['用户指标', '注册用户数', '累计注册用户', '10万（6个月）'],
            ['', '日活跃用户（DAU）', '当日登录/使用用户数', '5,000+'],
            ['', '月活跃用户（MAU）', '当月活跃用户数', '30,000+'],
            ['', 'DAU/MAU', '日活/月活', '>15%'],
            ['', '次日留存率', '次日活跃/新增', '>40%'],
            ['', '7日留存率', '7日后活跃/新增', '>20%'],
            ['', '30日留存率', '30日后活跃/新增', '>10%'],
            ['行为指标', '行程生成量', '累计生成行程数', '10万+（6个月）'],
            ['', '人均行程数', '行程生成量/活跃用户', '>3个/月'],
            ['', '行程完成率', '查看详情的行程/生成的行程', '>70%'],
            ['', '分享率', '分享行程数/生成行程数', '>10%'],
            ['', '对话轮次', '平均每次会话对话轮次', '>3轮'],
            ['商业指标', '付费转化率', '付费用户/活跃用户', '>3%'],
            ['', 'ARPU', '月收入/月活跃用户', '>5元'],
            ['', '会员续费率', '续费会员/到期会员', '>50%'],
            ['', '获客成本（CAC）', '获客投入/新增用户', '<20元'],
            ['', '用户生命周期价值（LTV）', '用户生命周期内总收入', '>100元'],
        ],
        col_widths=[1, 1.5, 2.2, 1.8]
    )
    
    add_title(doc, '5.2 数据看板', level=2)
    add_bullet(doc, '实时看板：在线用户数、行程生成量、API调用量、系统状态')
    add_bullet(doc, '日报：新增用户、活跃用户、行程生成、留存、转化')
    add_bullet(doc, '周报：周趋势、用户分层、内容数据、活动效果')
    add_bullet(doc, '月报：月度总结、目标达成、用户画像、收入分析')
    
    add_title(doc, '5.3 A/B测试', level=2)
    add_bullet(doc, '测试范围：首页布局、对话引导、行程展示、推荐算法、定价策略')
    add_bullet(doc, '测试流程：提出假设→设计实验→开发上线→数据收集→分析结论→全量/放弃')
    add_bullet(doc, '测试工具：自建A/B测试框架，按用户ID分流')
    add_bullet(doc, '显著性要求：置信度>95%，样本量足够，测试周期>7天')
    
    # 六、客服体系
    add_title(doc, '六、客服体系', level=1)
    
    add_title(doc, '6.1 客服渠道', level=2)
    add_bullet(doc, '在线客服：产品内在线客服，工作时间9:00-21:00')
    add_bullet(doc, '邮件客服：support@example.com，24小时内回复')
    add_bullet(doc, '社群客服：用户微信群/QQ群，社群管理员回复')
    add_bullet(doc, '帮助中心：常见问题FAQ、使用教程、视频教程')
    
    add_title(doc, '6.2 客服流程', level=2)
    add_bullet(doc, '问题分类：账号问题、行程问题、技术问题、建议反馈、其他')
    add_bullet(doc, '响应时效：在线客服<5分钟，邮件<24小时，社群<1小时')
    add_bullet(doc, '问题升级：普通问题→客服主管→产品经理→技术团队')
    add_bullet(doc, '问题闭环：记录问题→处理问题→用户确认→满意度评价→归档')
    
    add_title(doc, '6.3 用户反馈处理', level=2)
    add_bullet(doc, '反馈收集：产品内反馈入口、社群、客服、应用商店评论')
    add_bullet(doc, '反馈分类：功能建议、Bug反馈、体验问题、内容纠错、其他')
    add_bullet(doc, '处理流程：收集→分类→评估→排期→开发→上线→通知用户')
    add_bullet(doc, '反馈激励：有效反馈用户获得积分/会员奖励，被采纳的反馈额外奖励')
    
    # 七、运营节奏
    add_title(doc, '七、运营节奏', level=1)
    
    add_table(doc,
        ['时间', '重点工作', '关键产出', '负责人'],
        [
            ['第1月', '冷启动、种子用户、内容基础建设', '5000种子用户、2500景点数据', '运营负责人'],
            ['第2月', '用户增长、内容扩充、社群建设', '1万用户、5000景点、10个社群', '运营负责人'],
            ['第3月', 'KOL合作、活动运营、UGC上线', '3万用户、首场大型活动、UGC功能', '市场负责人'],
            ['第4月', '品牌传播、会员体系、商业化探索', '5万用户、会员体系上线、首笔收入', '产品负责人'],
            ['第5月', '数据优化、精细化运营、内容深化', '8万用户、A/B测试体系、内容质量提升', '数据负责人'],
            ['第6月', '目标冲刺、品牌升级、年度规划', '10万用户、品牌升级、下年度规划', '全体'],
        ],
        col_widths=[0.8, 2.2, 2.5, 1]
    )
    
    output_path = os.path.join(OUTPUT_DIR, '02_运营方案.docx')
    doc.save(output_path)
    print(f'已生成: {output_path}')
    return output_path


# ============================================================
# 3. 商业计划书
# ============================================================
def generate_business_plan():
    doc = Document()
    
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    
    add_title(doc, 'AI旅行规划产品商业计划书', level=0)
    doc.add_paragraph()
    
    add_doc_info(doc, 'AI旅行规划产品商业计划书', 'v1.0', '2026-09-03', '创始团队', '待评审')
    
    # 一、执行摘要
    add_title(doc, '一、执行摘要', level=1)
    
    add_title(doc, '1.1 项目概述', level=2)
    add_para(doc, 'AI旅行规划产品是一款基于大语言模型（LLM）和检索增强生成（RAG）技术的智能旅行规划工具。产品通过自然语言对话的方式，帮助用户快速生成个性化的旅行行程，提供景点推荐、路线规划、预算估算、预约提醒、避坑提示、人文介绍等全方位的旅行规划服务。')
    
    add_title(doc, '1.2 市场机会', level=2)
    add_para(doc, '中国旅游市场规模超过6万亿元，在线旅游用户超过5亿。然而，传统旅行规划方式存在信息过载、规划耗时、个性化不足等痛点。AI技术的成熟为旅行规划带来了革命性的变革，通过自然语言对话即可生成个性化行程，大幅降低规划门槛。')
    
    add_title(doc, '1.3 产品优势', level=2)
    add_bullet(doc, '技术领先：基于LLM+RAG技术，规划质量高，个性化强')
    add_bullet(doc, '知识库驱动：自建旅行知识库，数据质量可控，持续优化')
    add_bullet(doc, '人文特色：融入历史文化、名人故事、红色旅行等人文内容')
    add_bullet(doc, '规则引擎：自定义规划规则引擎，保证行程合理性和实用性')
    add_bullet(doc, '多端覆盖：Web端、移动端、管理后台，满足不同场景需求')
    
    add_title(doc, '1.4 商业模式', level=2)
    add_para(doc, '采用"免费+增值"的Freemium模式，基础功能免费使用，高级功能通过会员订阅付费。同时探索B端合作、广告收入、数据服务等多元化收入来源。')
    
    add_title(doc, '1.5 融资需求', level=2)
    add_table(doc,
        ['项目', '内容'],
        [
            ['融资轮次', '天使轮'],
            ['融资金额', '500万元人民币'],
            ['出让股权', '10%-15%'],
            ['资金用途', '产品研发40%、内容建设25%、市场推广25%、团队建设10%'],
            ['预计周期', '18个月'],
            ['里程碑', '10万用户、月收入10万、产品PMF验证'],
        ],
        col_widths=[1.5, 5]
    )
    
    # 二、市场分析
    add_title(doc, '二、市场分析', level=1)
    
    add_title(doc, '2.1 市场规模', level=2)
    add_table(doc,
        ['指标', '数值', '数据来源', '说明'],
        [
            ['中国旅游总收入', '6.2万亿元（2024年）', '文化和旅游部', '国内旅游+入境旅游'],
            ['国内旅游人次', '58.2亿人次（2024年）', '文化和旅游部', '同比增长15.4%'],
            ['在线旅游用户规模', '5.2亿人（2024年）', 'CNNIC', '在线旅行预订用户'],
            ['在线旅游市场规模', '1.8万亿元（2024年）', '易观分析', '在线旅游交易规模'],
            ['旅行规划工具市场', '约200亿元（2024年）', '行业估算', '攻略、工具、内容等'],
            ['AI旅行市场增速', '年均复合增长率45%', '行业预测', '2024-2028年'],
        ],
        col_widths=[1.5, 1.8, 1.2, 2]
    )
    
    add_title(doc, '2.2 市场趋势', level=2)
    add_bullet(doc, '个性化需求增长：用户越来越追求个性化、定制化的旅行体验，传统跟团游占比下降')
    add_bullet(doc, 'AI技术赋能：大语言模型技术成熟，AI在旅行规划中的应用逐渐普及')
    add_bullet(doc, '内容消费升级：用户不仅需要行程，还需要深度的人文、历史、文化内容')
    add_bullet(doc, '短途周边游兴起：周末游、周边游、微度假成为新的增长热点')
    add_bullet(doc, '红色旅行热潮：红色旅游、文化旅游、研学旅行持续增长')
    add_bullet(doc, '可持续旅行：环保旅行、负责任旅行逐渐受到关注')
    
    add_title(doc, '2.3 目标市场', level=2)
    add_table(doc,
        ['细分市场', '用户特征', '市场规模', '优先级'],
        [
            ['休闲游客', '偶尔出行，追求轻松体验，25-45岁', '约2亿人', 'P0'],
            ['亲子家庭', '带孩子出行，关注安全舒适，30-45岁', '约8000万人', 'P0'],
            ['情侣/朋友', '结伴出行，追求浪漫有趣，20-35岁', '约1.2亿人', 'P1'],
            ['深度玩家', '频繁出行，追求独特体验，25-40岁', '约3000万人', 'P1'],
            ['银发族', '退休后出行，关注健康舒适，55岁以上', '约5000万人', 'P2'],
            ['商务出行', '出差顺带旅行，关注效率，25-50岁', '约4000万人', 'P2'],
        ],
        col_widths=[1.2, 2.5, 1.2, 0.8]
    )
    
    # 三、产品介绍
    add_title(doc, '三、产品介绍', level=1)
    
    add_title(doc, '3.1 产品功能', level=2)
    add_bullet(doc, '智能对话：自然语言对话，意图识别，多轮交互')
    add_bullet(doc, '行程生成：基于LLM+RAG+规则引擎，生成个性化行程')
    add_bullet(doc, '行程展示：时间轴、地图、预算、预约提醒、避坑提示')
    add_bullet(doc, '行程调整：支持修改参数、增减景点、调整顺序')
    add_bullet(doc, '人文介绍：景点、历史、名人、红色旅行相关人文知识')
    add_bullet(doc, '地图探索：地图查看周边景点，搜索和筛选')
    add_bullet(doc, '行程分享：生成精美海报，分享到社交平台')
    add_bullet(doc, '管理后台：知识库管理、审核管理、用户管理、数据看板')
    
    add_title(doc, '3.2 技术架构', level=2)
    add_bullet(doc, '前端：Vue3 + TypeScript + Vite，用户端和管理后台分离')
    add_bullet(doc, '后端：Python + FastAPI，微服务架构，模块化设计')
    add_bullet(doc, 'AI：DeepSeek LLM + text2vec嵌入模型 + Chroma向量数据库')
    add_bullet(doc, '数据：MySQL（业务数据）+ Redis（缓存）+ Chroma（向量）')
    add_bullet(doc, '地图：腾讯地图/高德地图，双Provider兼容')
    add_bullet(doc, '部署：Docker容器化，Nginx反向代理，蓝绿部署')
    
    add_title(doc, '3.3 产品路线图', level=2)
    add_table(doc,
        ['阶段', '时间', '核心功能', '目标'],
        [
            ['MVP', '第1-3月', '对话、行程生成、基础展示、用户系统', '验证产品价值'],
            ['V1.0', '第4-6月', 'RAG知识库、人文介绍、预约提醒、避坑提示', '提升规划质量'],
            ['V1.5', '第7-9月', '地图探索、行程调整、分享海报、会员体系', '完善用户体验'],
            ['V2.0', '第10-12月', '社区UGC、达人合作、B端API、多语言', '商业化和生态'],
            ['V3.0', '第13-18月', 'AI旅行助手、智能推荐、实时行程、VR/AR', '技术领先'],
        ],
        col_widths=[0.8, 1, 2.8, 1.9]
    )
    
    # 四、商业模式
    add_title(doc, '四、商业模式', level=1)
    
    add_title(doc, '4.1 收入来源', level=2)
    add_table(doc,
        ['收入类型', '具体内容', '定价策略', '收入占比预估'],
        [
            ['会员订阅', '月度/季度/年度会员，更多行程次数、高级功能', '月费19元，季费49元，年费168元', '50%'],
            ['单次付费', '高级行程生成、深度攻略、专业规划师服务', '5-50元/次', '15%'],
            ['B端合作', '为旅行社、酒店、景区提供API和定制服务', '按调用量/定制费', '20%'],
            ['广告收入', '景点、酒店、餐厅推荐广告，原生广告', 'CPM/CPC/CPA', '10%'],
            ['数据服务', '旅行趋势报告、用户画像分析、行业研究', '按报告/订阅', '5%'],
        ],
        col_widths=[1, 2.5, 2, 1]
    )
    
    add_title(doc, '4.2 会员权益设计', level=2)
    add_table(doc,
        ['权益', '免费用户', '月度会员', '年度会员'],
        [
            ['每日行程生成次数', '3次', '20次', '无限次'],
            ['行程调整次数', '1次/行程', '5次/行程', '无限次'],
            ['高级功能（人文深度、预算精细）', '基础', '完整', '完整+优先'],
            ['行程导出（PDF/图片）', '带水印', '无水印', '无水印+多种模板'],
            ['客服响应', '邮件', '优先邮件', '专属客服'],
            ['新功能体验', '延后', '提前', '优先内测'],
            ['广告', '有', '无', '无'],
        ],
        col_widths=[2.2, 1.3, 1.3, 1.7]
    )
    
    add_title(doc, '4.3 成本结构', level=2)
    add_table(doc,
        ['成本类型', '具体内容', '占比', '说明'],
        [
            ['研发成本', '团队薪资、服务器、技术服务', '40%', '最大成本项'],
            ['内容成本', '知识库建设、数据采购、内容审核', '20%', '持续投入'],
            ['营销成本', '广告投放、KOL合作、活动运营', '25%', '用户增长期较高'],
            ['运营成本', '客服、办公、法务、财务', '10%', '基础运营'],
            ['其他成本', '税费、保险、不可预见费', '5%', '预留'],
        ],
        col_widths=[1.2, 2.5, 0.8, 2]
    )
    
    # 五、竞争分析
    add_title(doc, '五、竞争分析', level=1)
    
    add_title(doc, '5.1 竞争格局', level=2)
    add_table(doc,
        ['竞品类型', '代表产品', '优势', '劣势', '威胁程度'],
        [
            ['OTA平台', '携程、去哪儿、飞猪', '流量大、资源全、交易闭环', '规划能力弱、个性化不足、广告多', '中'],
            ['内容平台', '马蜂窝、小红书、抖音', '内容丰富、用户活跃、种草能力强', '规划工具弱、信息分散、广告泛滥', '中'],
            ['AI工具', 'Trip.com AI、妙计旅行、AI行程助手', 'AI能力强、规划效率高', '内容积累少、用户量小、商业化弱', '高'],
            ['传统工具', '穷游行程助手、出发吧', '功能成熟、用户基础好', '技术老旧、体验差、无AI能力', '低'],
            ['地图工具', '高德地图、百度地图', '地图能力强、POI数据全', '行程规划弱、无内容、无社交', '低'],
        ],
        col_widths=[1, 1.8, 1.8, 1.8, 0.8]
    )
    
    add_title(doc, '5.2 差异化优势', level=2)
    add_bullet(doc, 'AI+RAG双引擎：不仅有LLM的生成能力，还有RAG的知识检索能力，规划质量更高')
    add_bullet(doc, '知识库自建：自建旅行知识库，数据质量可控，持续优化，不依赖第三方')
    add_bullet(doc, '人文特色：融入历史文化、名人故事、红色旅行等深度人文内容')
    add_bullet(doc, '规则引擎：自定义规划规则引擎，保证行程合理性、实用性、可解释性')
    add_bullet(doc, '纯规划定位：不做交易，专注规划，中立客观，用户信任度高')
    add_bullet(doc, 'B端能力：管理后台完善，知识库可管理，适合B端合作和定制')
    
    # 六、营销策略
    add_title(doc, '六、营销策略', level=1)
    
    add_title(doc, '6.1 品牌定位', level=2)
    add_para(doc, '品牌口号："让旅行规划更简单"。品牌形象：智能、专业、有温度的旅行规划助手。核心价值：用AI技术降低旅行规划门槛，让每个人都能轻松规划完美的旅行。')
    
    add_title(doc, '6.2 获客渠道', level=2)
    add_table(doc,
        ['渠道', '方式', '成本', '效果预估', '优先级'],
        [
            ['内容营销', '小红书、抖音、公众号、知乎', '中', '高（高质量用户）', 'P0'],
            ['KOL合作', '旅行达人、博主、KOC', '中高', '高（口碑传播）', 'P0'],
            ['搜索引擎', 'SEO、SEM', '中', '中（精准用户）', 'P1'],
            ['应用商店', 'ASO、推荐位', '低', '中（自然流量）', 'P1'],
            ['社群运营', '微信群、QQ群、豆瓣小组', '低', '中（精准用户）', 'P1'],
            ['裂变增长', '分享奖励、邀请奖励', '低', '中（病毒传播）', 'P2'],
            ['线下合作', '旅行社、酒店、景区合作', '高', '中（B端流量）', 'P2'],
        ],
        col_widths=[1, 2, 0.8, 1.5, 0.8]
    )
    
    add_title(doc, '6.3 品牌建设', level=2)
    add_bullet(doc, '内容品牌：打造"AI旅行研究所"内容品牌，发布旅行攻略、行业洞察')
    add_bullet(doc, 'IP形象：设计品牌IP形象，用于产品、内容、周边')
    add_bullet(doc, '社区建设：建立用户社区，培养核心用户，形成品牌文化')
    add_bullet(doc, '行业影响力：参加行业会议、发布行业报告、与媒体合作')
    
    # 七、运营计划
    add_title(doc, '七、运营计划', level=1)
    
    add_title(doc, '7.1 团队规划', level=2)
    add_table(doc,
        ['阶段', '时间', '团队规模', '核心岗位'],
        [
            ['初创期', '第1-6月', '8人', '产品1、后端2、前端2、算法1、运营1、设计1'],
            ['成长期', '第7-12月', '15人', '增加：内容运营2、市场1、客服1、测试1、销售1'],
            ['扩张期', '第13-18月', '25人', '增加：B端团队3、数据团队2、管理团队2'],
        ],
        col_widths=[1, 1, 1, 4.5]
    )
    
    add_title(doc, '7.2 关键里程碑', level=2)
    add_table(doc,
        ['时间', '里程碑', '关键指标'],
        [
            ['第1月', '产品MVP上线', '核心功能可用，种子用户100人'],
            ['第3月', '产品V1.0发布', '注册用户5000，日活500，行程生成5000'],
            ['第6月', 'PMF验证完成', '注册用户3万，日活2000，月留存20%，首笔收入'],
            ['第9月', '会员体系上线', '注册用户6万，付费用户1000，月收入5万'],
            ['第12月', 'B端业务启动', '注册用户10万，B端客户10家，月收入20万'],
            ['第18月', 'A轮融资准备', '注册用户30万，月收入100万，盈亏平衡'],
        ],
        col_widths=[0.8, 1.8, 3.9]
    )
    
    # 八、团队介绍
    add_title(doc, '八、团队介绍', level=1)
    
    add_title(doc, '8.1 核心团队', level=2)
    add_table(doc,
        ['职位', '人数', '职责', '能力要求'],
        [
            ['CEO/产品负责人', '1', '产品战略、融资、团队管理', '旅行行业经验、产品能力、领导力'],
            ['CTO/技术负责人', '1', '技术架构、技术团队管理', 'AI/大数据背景、架构能力、管理经验'],
            ['后端工程师', '2', '后端开发、API设计、性能优化', 'Python/FastAPI、MySQL、微服务'],
            ['前端工程师', '2', '前端开发、用户体验优化', 'Vue3/TypeScript、地图开发'],
            ['算法工程师', '1', 'LLM应用、RAG、推荐算法', 'NLP/LLM经验、向量检索'],
            ['运营负责人', '1', '用户运营、内容运营、活动运营', '互联网运营经验、旅行行业经验'],
            ['UI/UX设计师', '1', '产品设计、交互设计、视觉设计', '移动端设计、设计系统'],
        ],
        col_widths=[1.5, 0.6, 2.2, 2.2]
    )
    
    add_title(doc, '8.2 顾问团队', level=2)
    add_bullet(doc, '旅行行业顾问：资深旅行行业专家，提供行业洞察和资源对接')
    add_bullet(doc, 'AI技术顾问：AI领域专家，提供技术方向指导和算法优化建议')
    add_bullet(doc, '法律顾问：互联网法律专家，提供合规、知识产权、融资法律咨询')
    add_bullet(doc, '财务顾问：资深财务专家，提供财务规划、融资、税务咨询')
    
    # 九、财务预测
    add_title(doc, '九、财务预测', level=1)
    
    add_title(doc, '9.1 收入预测', level=2)
    add_table(doc,
        ['项目', '第1年', '第2年', '第3年'],
        [
            ['注册用户数', '10万', '50万', '200万'],
            ['月活跃用户', '2万', '10万', '40万'],
            ['付费用户数', '2000', '2万', '10万'],
            ['会员收入', '30万', '300万', '1500万'],
            ['单次付费收入', '10万', '100万', '500万'],
            ['B端合作收入', '5万', '150万', '800万'],
            ['广告收入', '5万', '80万', '400万'],
            ['数据服务收入', '0', '20万', '200万'],
            ['总收入', '50万', '650万', '3400万'],
        ],
        col_widths=[2, 1.5, 1.5, 1.5]
    )
    
    add_title(doc, '9.2 成本预测', level=2)
    add_table(doc,
        ['项目', '第1年', '第2年', '第3年'],
        [
            ['研发成本', '200万', '500万', '1000万'],
            ['内容成本', '80万', '200万', '400万'],
            ['营销成本', '100万', '300万', '600万'],
            ['运营成本', '50万', '120万', '250万'],
            ['其他成本', '20万', '50万', '100万'],
            ['总成本', '450万', '1170万', '2350万'],
        ],
        col_widths=[2, 1.5, 1.5, 1.5]
    )
    
    add_title(doc, '9.3 利润预测', level=2)
    add_table(doc,
        ['项目', '第1年', '第2年', '第3年'],
        [
            ['总收入', '50万', '650万', '3400万'],
            ['总成本', '450万', '1170万', '2350万'],
            ['毛利润', '-400万', '-520万', '1050万'],
            ['毛利率', '-800%', '-80%', '31%'],
            ['净利润', '-420万', '-550万', '900万'],
            ['净利率', '-840%', '-85%', '26%'],
        ],
        col_widths=[2, 1.5, 1.5, 1.5]
    )
    
    add_para(doc, '注：第1-2年为投入期，预计亏损；第3年实现盈利。盈亏平衡点预计在第28个月左右。')
    
    # 十、融资计划
    add_title(doc, '十、融资计划', level=1)
    
    add_title(doc, '10.1 融资历史', level=2)
    add_para(doc, '目前为创始团队自筹资金，已投入约100万元用于产品研发和初期运营。')
    
    add_title(doc, '10.2 本轮融资', level=2)
    add_table(doc,
        ['项目', '内容'],
        [
            ['融资轮次', '天使轮'],
            ['融资金额', '500万元人民币'],
            ['出让股权', '10%-15%'],
            ['投前估值', '3000万-4500万元'],
            ['资金用途', '产品研发40%（200万）、内容建设25%（125万）、市场推广25%（125万）、团队建设10%（50万）'],
            ['预计周期', '18个月'],
            ['里程碑', '10万用户、月收入10万、产品PMF验证、A轮融资准备'],
        ],
        col_widths=[1.5, 5]
    )
    
    add_title(doc, '10.3 资金使用计划', level=2)
    add_table(doc,
        ['用途', '金额', '占比', '说明'],
        [
            ['产品研发', '200万', '40%', '团队薪资、服务器、技术服务、AI模型费用'],
            ['内容建设', '125万', '25%', '知识库数据采购、内容审核、UGC激励'],
            ['市场推广', '125万', '25%', '广告投放、KOL合作、活动运营、品牌建设'],
            ['团队建设', '50万', '10%', '招聘、培训、办公、法务、财务'],
        ],
        col_widths=[1.2, 1, 0.8, 3.5]
    )
    
    add_title(doc, '10.4 下一轮融资计划', level=2)
    add_para(doc, '预计在第18个月左右启动A轮融资，目标融资2000万-3000万元，用于团队扩张、市场推广、B端业务拓展、国际化探索。')
    
    # 十一、风险分析
    add_title(doc, '十一、风险分析', level=1)
    
    add_table(doc,
        ['风险类型', '风险描述', '影响程度', '发生概率', '应对措施'],
        [
            ['技术风险', 'LLM API不稳定、成本超预算、规划质量不达预期', '高', '中', '多模型备份、缓存优化、规则引擎兜底、持续优化提示词'],
            ['市场风险', '竞品进入、用户接受度低、市场需求变化', '高', '中', '快速迭代、建立壁垒、差异化定位、用户反馈驱动'],
            ['内容风险', '知识库覆盖不足、数据质量差、版权问题、信息过时', '高', '中', '严格审核、多源验证、持续更新、版权合规'],
            ['合规风险', '数据安全、用户隐私、内容合规、AI监管', '高', '低', '安全加固、隐私保护、内容审核、关注政策'],
            ['团队风险', '核心人员流失、团队扩张过快、管理能力不足', '中', '中', '股权激励、文化建设、合理招聘、管理培训'],
            ['资金风险', '融资不顺利、现金流紧张、成本超预算', '高', '中', '精简开支、多元化收入、提前融资、现金流管理'],
            ['竞争风险', '大厂进入、价格战、用户被抢夺', '高', '中', '建立壁垒、快速增长、差异化竞争、合作共赢'],
        ],
        col_widths=[0.9, 2.5, 0.8, 0.8, 2.5]
    )
    
    # 十二、附录
    add_title(doc, '十二、附录', level=1)
    
    add_title(doc, '12.1 术语表', level=2)
    add_table(doc,
        ['术语', '说明'],
        [
            ['LLM', '大语言模型（Large Language Model）'],
            ['RAG', '检索增强生成（Retrieval-Augmented Generation）'],
            ['PMF', '产品市场契合（Product-Market Fit）'],
            ['MVP', '最小可行产品（Minimum Viable Product）'],
            ['OTA', '在线旅行社（Online Travel Agency）'],
            ['UGC', '用户生成内容（User Generated Content）'],
            ['KOL', '关键意见领袖（Key Opinion Leader）'],
            ['KOC', '关键意见消费者（Key Opinion Consumer）'],
            ['CAC', '用户获取成本（Customer Acquisition Cost）'],
            ['LTV', '用户生命周期价值（Life Time Value）'],
            ['ARPU', '每用户平均收入（Average Revenue Per User）'],
            ['DAU/MAU', '日活跃用户/月活跃用户'],
        ],
        col_widths=[1.5, 5]
    )
    
    add_title(doc, '12.2 参考资料', level=2)
    add_bullet(doc, '《2024年中国旅游经济运行分析》- 中国旅游研究院')
    add_bullet(doc, '《2024年中国在线旅游行业报告》- 易观分析')
    add_bullet(doc, '《AI+旅游行业发展白皮书》- 艾瑞咨询')
    add_bullet(doc, '《大语言模型在旅行规划中的应用研究》- 行业研究报告')
    
    output_path = os.path.join(OUTPUT_DIR, '03_商业计划书.docx')
    doc.save(output_path)
    print(f'已生成: {output_path}')
    return output_path


# ============================================================
# 4. 竞品分析报告
# ============================================================
def generate_competitor_analysis():
    doc = Document()
    
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    
    add_title(doc, 'AI旅行规划产品竞品分析报告', level=0)
    doc.add_paragraph()
    
    add_doc_info(doc, 'AI旅行规划产品竞品分析报告', 'v1.0', '2026-09-03', '产品团队', '待评审')
    
    # 一、分析概述
    add_title(doc, '一、分析概述', level=1)
    
    add_title(doc, '1.1 分析目的', level=2)
    add_para(doc, '通过对旅行规划领域主要竞品的深入分析，了解市场竞争格局，识别竞品优劣势，发现市场机会和差异化空间，为本产品的产品定位、功能设计、运营策略提供参考依据。')
    
    add_title(doc, '1.2 分析范围', level=2)
    add_bullet(doc, '时间范围：2024年-2026年')
    add_bullet(doc, '地域范围：中国市场为主，兼顾全球趋势')
    add_bullet(doc, '竞品类型：OTA平台、内容平台、AI工具、传统规划工具、地图工具')
    add_bullet(doc, '分析维度：产品功能、用户体验、技术能力、内容质量、商业模式、运营策略')
    
    add_title(doc, '1.3 竞品选择', level=2)
    add_table(doc,
        ['竞品类型', '代表产品', '选择理由'],
        [
            ['OTA平台', '携程、去哪儿、飞猪', '旅行行业头部平台，流量和资源优势明显'],
            ['内容平台', '马蜂窝、小红书', '旅行内容社区，用户活跃度高，种草能力强'],
            ['AI工具', 'Trip.com AI、妙计旅行、豆包旅行助手', 'AI旅行规划领域的直接竞争者'],
            ['传统工具', '穷游行程助手、出发吧', '传统行程规划工具，有一定用户基础'],
            ['地图工具', '高德地图、百度地图', '地图和POI数据优势，有行程规划功能'],
        ],
        col_widths=[1.2, 2.5, 2.8]
    )
    
    # 二、竞品详细分析
    add_title(doc, '二、竞品详细分析', level=1)
    
    add_title(doc, '2.1 OTA平台：携程', level=2)
    
    add_title(doc, '2.1.1 产品概述', level=3)
    add_para(doc, '携程是中国最大的在线旅游平台，提供酒店、机票、火车票、门票、度假产品等全方位旅行服务。近年来推出AI旅行助手功能，开始布局AI旅行规划领域。')
    
    add_title(doc, '2.1.2 核心功能', level=3)
    add_bullet(doc, 'AI旅行助手：基于大模型的对话式旅行规划，支持自然语言输入')
    add_bullet(doc, '行程规划：生成包含交通、住宿、景点的完整行程，可直接预订')
    add_bullet(doc, '智能推荐：基于用户偏好和历史行为推荐酒店、景点、餐厅')
    add_bullet(doc, '实时查询：机票、酒店、门票实时价格和库存查询')
    add_bullet(doc, '行程管理：订单管理、行程提醒、在线客服')
    
    add_title(doc, '2.1.3 优势', level=3)
    add_bullet(doc, '流量优势：月活跃用户超过1亿，品牌知名度高')
    add_bullet(doc, '资源优势：酒店、机票、门票等供应链资源丰富')
    add_bullet(doc, '交易闭环：从规划到预订到售后的完整闭环')
    add_bullet(doc, '数据积累：海量用户行为数据和交易数据')
    add_bullet(doc, '资金实力：上市公司，资金充足，可持续投入AI')
    
    add_title(doc, '2.1.4 劣势', level=3)
    add_bullet(doc, '规划能力弱：AI规划还在早期，行程质量和个性化不足')
    add_bullet(doc, '商业化导向：推荐受佣金影响，中立性不足，广告多')
    add_bullet(doc, '内容薄弱：攻略和人文内容不足，主要依赖UGC')
    add_bullet(doc, '体验复杂：产品功能多，信息过载，规划流程不够简洁')
    add_bullet(doc, '创新慢：大公司体制，产品迭代速度慢，创新能力有限')
    
    add_title(doc, '2.2 内容平台：马蜂窝', level=2)
    
    add_title(doc, '2.2.1 产品概述', level=3)
    add_para(doc, '马蜂窝是中国领先的旅行内容社区，以UGC攻略和游记为核心，提供旅行攻略、景点评价、酒店预订、旅游产品等服务。')
    
    add_title(doc, '2.2.2 核心功能', level=3)
    add_bullet(doc, '攻略社区：海量UGC攻略、游记、问答，内容丰富')
    add_bullet(doc, '行程助手：基于攻略内容生成行程，可手动调整')
    add_bullet(doc, '景点评价：用户真实评价和评分，参考价值高')
    add_bullet(doc, '酒店预订：接入酒店库存，可直接预订')
    add_bullet(doc, '旅游产品：跟团游、自由行、当地玩乐等产品')
    
    add_title(doc, '2.2.3 优势', level=3)
    add_bullet(doc, '内容丰富：海量UGC内容，攻略和游记质量高')
    add_bullet(doc, '用户活跃：社区氛围好，用户粘性高，内容生产活跃')
    add_bullet(doc, '种草能力强：用户决策影响大，旅行种草首选平台')
    add_bullet(doc, '数据真实：用户真实评价和体验，可信度高')
    add_bullet(doc, '品牌认知：旅行内容领域品牌知名度高')
    
    add_title(doc, '2.2.4 劣势', level=3)
    add_bullet(doc, '规划能力弱：行程助手功能简单，无AI能力，手动调整繁琐')
    add_bullet(doc, '信息分散：攻略内容分散，需要用户自行筛选和整合')
    add_bullet(doc, '广告泛滥：内容中广告和软文多，影响体验')
    add_bullet(doc, '交易弱：预订体验不如OTA，供应链资源有限')
    add_bullet(doc, '内容质量参差：UGC内容质量参差不齐，需要筛选')
    
    add_title(doc, '2.3 AI工具：Trip.com AI（携程国际版）', level=2)
    
    add_title(doc, '2.3.1 产品概述', level=3)
    add_para(doc, 'Trip.com是携程的国际版，推出了AI旅行助手功能，基于大语言模型提供对话式旅行规划服务，是目前AI旅行规划领域的代表性产品。')
    
    add_title(doc, '2.3.2 核心功能', level=3)
    add_bullet(doc, '对话式规划：自然语言对话，多轮交互，逐步完善行程')
    add_bullet(doc, '智能行程：生成包含航班、酒店、景点的完整行程')
    add_bullet(doc, '实时查询：实时查询航班、酒店、景点价格和信息')
    add_bullet(doc, '个性化推荐：基于用户偏好推荐景点、餐厅、活动')
    add_bullet(doc, '行程管理：行程保存、分享、导出')
    
    add_title(doc, '2.3.3 优势', level=3)
    add_bullet(doc, 'AI能力强：基于大模型，对话体验好，理解能力强')
    add_bullet(doc, '实时数据：接入实时航班、酒店、景点数据')
    add_bullet(doc, '交易闭环：可直接预订，从规划到交易无缝衔接')
    add_bullet(doc, '多语言支持：支持多种语言，国际化程度高')
    add_bullet(doc, '携程背书：背靠携程，资源和资金充足')
    
    add_title(doc, '2.3.4 劣势', level=3)
    add_bullet(doc, '国内体验差：主要面向国际市场，国内数据和体验不足')
    add_bullet(doc, '规划质量一般：行程较为模板化，个性化和深度不足')
    add_bullet(doc, '人文内容少：缺少历史文化、景点介绍等深度内容')
    add_bullet(doc, '商业化导向：推荐受佣金影响，中立性不足')
    add_bullet(doc, '中文优化不足：中文理解和表达不如国内产品')
    
    add_title(doc, '2.4 传统工具：穷游行程助手', level=2)
    
    add_title(doc, '2.4.1 产品概述', level=3)
    add_para(doc, '穷游行程助手是穷游网推出的行程规划工具，帮助用户规划和管理旅行行程，是传统行程规划工具的代表。')
    
    add_title(doc, '2.4.2 核心功能', level=3)
    add_bullet(doc, '行程规划：手动添加景点、酒店、交通，拖拽调整顺序')
    add_bullet(doc, '模板行程：提供热门目的地的经典行程模板，可直接使用')
    add_bullet(doc, '地图展示：地图可视化行程，计算距离和时间')
    add_bullet(doc, '行程导出：导出为PDF、Excel，支持打印')
    add_bullet(doc, '社区分享：行程分享到社区，其他用户可参考和复制')
    
    add_title(doc, '2.4.3 优势', level=3)
    add_bullet(doc, '功能成熟：经过多年迭代，功能完善，稳定性好')
    add_bullet(doc, '用户基础：有一定的用户基础和社区积累')
    add_bullet(doc, '手动灵活：手动规划灵活度高，用户完全控制')
    add_bullet(doc, '模板丰富：热门目的地模板多，可快速起步')
    add_bullet(doc, '导出方便：支持多种格式导出，便于打印和分享')
    
    add_title(doc, '2.4.4 劣势', level=3)
    add_bullet(doc, '无AI能力：完全手动规划，效率低，学习成本高')
    add_bullet(doc, '体验老旧：UI/UX设计老旧，不符合现代用户习惯')
    add_bullet(doc, '更新缓慢：产品迭代慢，新功能少')
    add_bullet(doc, '数据不全：景点和POI数据不够全面，更新不及时')
    add_bullet(doc, '移动端差：移动端体验差，主要依赖PC端')
    
    # 三、功能对比矩阵
    add_title(doc, '三、功能对比矩阵', level=1)
    
    add_table(doc,
        ['功能维度', '本产品', '携程', '马蜂窝', 'Trip.com AI', '穷游行程助手'],
        [
            ['对话式规划', '✅ 核心功能', '✅ 有', '❌ 无', '✅ 核心功能', '❌ 无'],
            ['AI行程生成', '✅ LLM+RAG+规则', '✅ 基础AI', '❌ 无', '✅ LLM', '❌ 手动'],
            ['个性化推荐', '✅ 多维度', '✅ 基于行为', '✅ 基于内容', '✅ 基于偏好', '❌ 无'],
            ['人文介绍', '✅ 深度人文', '❌ 少', '✅ UGC攻略', '❌ 少', '❌ 无'],
            ['预约提醒', '✅ 自动识别', '✅ 有', '❌ 无', '✅ 有', '❌ 无'],
            ['避坑提示', '✅ 知识库', '❌ 少', '✅ UGC', '❌ 少', '❌ 无'],
            ['地图展示', '✅ 路线+点位', '✅ 基础', '✅ 基础', '✅ 基础', '✅ 基础'],
            ['预算估算', '✅ 明细', '✅ 实时价格', '❌ 无', '✅ 实时价格', '✅ 手动'],
            ['行程调整', '✅ 对话+手动', '✅ 手动', '✅ 手动', '✅ 对话', '✅ 手动'],
            ['行程分享', '✅ 海报+链接', '✅ 链接', '✅ 社区', '✅ 链接', '✅ PDF'],
            ['知识库管理', '✅ 后台管理', '❌ 无', '✅ UGC', '❌ 无', '❌ 无'],
            ['数据可控', '✅ 自建库', '❌ 依赖供应商', '❌ UGC', '❌ 依赖供应商', '❌ 无'],
            ['交易闭环', '❌ 纯规划', '✅ 完整', '✅ 部分', '✅ 完整', '❌ 无'],
            ['实时价格', '❌ 无', '✅ 有', '❌ 无', '✅ 有', '❌ 无'],
            ['移动端体验', '✅ 响应式', '✅ App+小程序', '✅ App', '✅ App', '❌ 差'],
        ],
        col_widths=[1.2, 1.1, 1, 1, 1.2, 1.2]
    )
    
    # 四、优劣势总结
    add_title(doc, '四、优劣势总结', level=1)
    
    add_title(doc, '4.1 竞品共同优势', level=2)
    add_bullet(doc, '用户基础：头部竞品都有大量用户，品牌知名度高')
    add_bullet(doc, '资源丰富：OTA平台有供应链资源，内容平台有内容资源')
    add_bullet(doc, '资金充足：上市公司或大公司，资金实力强')
    add_bullet(doc, '数据积累：多年运营积累了大量用户数据和内容数据')
    
    add_title(doc, '4.2 竞品共同劣势', level=2)
    add_bullet(doc, '规划能力弱：大多数竞品的行程规划能力还比较基础，AI应用浅')
    add_bullet(doc, '个性化不足：行程模板化，缺乏真正的个性化和定制化')
    add_bullet(doc, '人文内容少：缺少深度的历史、文化、人文介绍')
    add_bullet(doc, '商业化导向：推荐受佣金影响，中立性不足，广告多')
    add_bullet(doc, '创新缓慢：大公司体制，产品迭代慢，创新能力有限')
    add_bullet(doc, '数据不可控：依赖第三方数据，质量和稳定性不可控')
    
    add_title(doc, '4.3 本产品差异化优势', level=2)
    add_table(doc,
        ['优势维度', '具体表现', '竞争价值'],
        [
            ['技术领先', 'LLM+RAG+规则引擎三引擎，规划质量高', '技术壁垒，难以复制'],
            ['知识库自建', '自建旅行知识库，数据质量可控，持续优化', '数据壁垒，长期竞争力'],
            ['人文特色', '深度人文介绍，历史文化名人故事', '差异化定位，用户粘性'],
            ['纯规划定位', '不做交易，中立客观，用户信任度高', '品牌信任，口碑传播'],
            ['规则引擎', '自定义规划规则，行程合理可解释', '质量保证，用户信任'],
            ['B端能力', '完善的管理后台，知识库可管理可定制', 'B端合作，多元化收入'],
            ['快速迭代', '小团队，决策快，产品迭代速度快', '敏捷创新，快速响应'],
        ],
        col_widths=[1.2, 3, 2.3]
    )
    
    # 五、机会与威胁
    add_title(doc, '五、机会与威胁', level=1)
    
    add_title(doc, '5.1 市场机会', level=2)
    add_bullet(doc, 'AI技术成熟：大语言模型技术成熟，AI旅行规划成为可能，用户接受度提高')
    add_bullet(doc, '个性化需求：用户越来越追求个性化旅行，传统跟团游和模板行程无法满足')
    add_bullet(doc, '内容消费升级：用户不仅需要行程，还需要深度的人文、历史、文化内容')
    add_bullet(doc, '规划工具空白：市场上缺少专注旅行规划、规划质量高的工具型产品')
    add_bullet(doc, 'B端需求旺盛：旅行社、酒店、景区需要AI规划工具提升服务效率')
    add_bullet(doc, '红色旅行热潮：红色旅游、文化旅游、研学旅行持续增长，需要专业规划')
    add_bullet(doc, '下沉市场：三四线城市用户旅行需求增长，规划能力不足，需要工具辅助')
    
    add_title(doc, '5.2 市场威胁', level=2)
    add_bullet(doc, '大厂进入：携程、美团、字节等大厂可能加大AI旅行规划投入')
    add_bullet(doc, '价格战：竞品可能通过免费或低价策略抢夺用户')
    add_bullet(doc, '技术同质化：AI技术门槛降低，竞品容易复制核心功能')
    add_bullet(doc, '数据壁垒：头部竞品有数据优势，后发者数据积累困难')
    add_bullet(doc, '政策监管：AI监管政策可能收紧，数据合规要求提高')
    add_bullet(doc, '用户习惯：用户习惯了OTA平台一站式服务，纯工具获客困难')
    
    # 六、竞争策略建议
    add_title(doc, '六、竞争策略建议', level=1)
    
    add_title(doc, '6.1 差异化定位', level=2)
    add_bullet(doc, '定位：专注旅行规划的AI工具，不做交易，保持中立客观')
    add_bullet(doc, '特色：人文+规划，不仅规划行程，还提供深度人文内容')
    add_bullet(doc, '用户：追求品质、喜欢深度旅行的中高端用户')
    add_bullet(doc, '价值：用AI技术降低规划门槛，提升旅行体验')
    
    add_title(doc, '6.2 产品策略', level=2)
    add_bullet(doc, '聚焦核心：把行程规划做到极致，规划质量是核心竞争力')
    add_bullet(doc, '内容驱动：自建知识库，持续优化内容质量，形成内容壁垒')
    add_bullet(doc, '人文特色：深度人文介绍，历史文化名人故事，差异化竞争')
    add_bullet(doc, '用户体验：简洁易用的对话式交互，降低使用门槛')
    add_bullet(doc, '快速迭代：小步快跑，持续优化，用户反馈驱动产品改进')
    
    add_title(doc, '6.3 运营策略', level=2)
    add_bullet(doc, '内容营销：通过旅行攻略、人文内容吸引用户，建立品牌认知')
    add_bullet(doc, 'KOL合作：与旅行达人、人文博主合作，口碑传播')
    add_bullet(doc, '社群运营：建立用户社群，培养核心用户，收集反馈')
    add_bullet(doc, 'UGC激励：鼓励用户分享行程和攻略，丰富内容生态')
    add_bullet(doc, 'B端合作：与旅行社、酒店、景区合作，拓展B端收入')
    
    add_title(doc, '6.4 技术策略', level=2)
    add_bullet(doc, '技术领先：持续优化AI模型和RAG技术，保持技术领先')
    add_bullet(doc, '数据壁垒：自建知识库，数据质量和覆盖度是核心壁垒')
    add_bullet(doc, '规则引擎：持续完善规划规则，提升行程合理性和实用性')
    add_bullet(doc, '多模型：支持多LLM模型，避免单一依赖，降低成本')
    add_bullet(doc, '开放API：开放规划能力API，支持B端合作和生态建设')
    
    # 七、总结
    add_title(doc, '七、总结', level=1)
    
    add_para(doc, '通过对旅行规划领域主要竞品的深入分析，可以看出：')
    
    add_bullet(doc, '市场机会大：旅行规划市场规模大，AI技术带来革命性变革，现有竞品规划能力普遍较弱，存在明显的市场空白')
    add_bullet(doc, '差异化空间大：本产品在AI技术、知识库、人文内容、规则引擎、纯规划定位等方面具有明显差异化优势')
    add_bullet(doc, '竞争压力存在：头部竞品有用户、资源、资金优势，可能加大AI投入，需要快速建立壁垒')
    add_bullet(doc, '核心竞争力：规划质量+内容质量+用户体验是核心竞争力，需要持续投入和优化')
    
    add_para(doc, '建议本产品聚焦旅行规划核心功能，以AI技术和知识库为壁垒，以人文内容为特色，快速迭代，建立用户口碑，逐步扩大市场份额。同时探索B端合作和多元化收入，实现可持续发展。')
    
    output_path = os.path.join(OUTPUT_DIR, '04_竞品分析报告.docx')
    doc.save(output_path)
    print(f'已生成: {output_path}')
    return output_path


# ============================================================
# 5. 用户旅程地图
# ============================================================
def generate_user_journey():
    doc = Document()
    
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    
    add_title(doc, 'AI旅行规划产品用户旅程地图', level=0)
    doc.add_paragraph()
    
    add_doc_info(doc, 'AI旅行规划产品用户旅程地图', 'v1.0', '2026-09-03', '产品团队', '待评审')
    
    # 一、用户画像
    add_title(doc, '一、用户画像', level=1)
    
    add_title(doc, '1.1 核心用户画像', level=2)
    add_table(doc,
        ['维度', '描述'],
        [
            ['姓名', '小李（典型用户）'],
            ['年龄', '28岁'],
            ['职业', '互联网公司产品经理'],
            ['收入', '月薪15K-25K'],
            ['城市', '一线城市（北京/上海/广州/深圳）'],
            ['旅行频率', '每年3-5次，包括1-2次长途旅行和多次周边游'],
            ['旅行风格', '喜欢深度游、人文游，追求品质和体验，不喜欢跟团'],
            ['规划痛点', '信息过载、规划耗时、个性化不足、容易踩坑'],
            ['技术能力', '熟悉互联网产品，愿意尝试新工具，对AI有好奇心'],
            ['消费能力', '中等偏上，愿意为好的体验和服务付费'],
        ],
        col_widths=[1.2, 5.3]
    )
    
    add_title(doc, '1.2 用户细分', level=2)
    add_table(doc,
        ['用户类型', '占比', '特征', '核心需求'],
        [
            ['休闲游客', '40%', '偶尔出行，追求轻松，25-45岁', '简单易用、经典路线、避坑提示'],
            ['亲子家庭', '20%', '带孩子出行，关注安全舒适，30-45岁', '亲子景点、行程宽松、设施完善'],
            ['情侣/朋友', '15%', '结伴出行，追求浪漫有趣，20-35岁', '打卡景点、美食推荐、拍照胜地'],
            ['深度玩家', '15%', '频繁出行，追求独特体验，25-40岁', '个性化、小众景点、深度攻略'],
            ['银发族', '10%', '退休后出行，关注健康舒适，55岁以上', '经典景点、行程轻松、服务周到'],
        ],
        col_widths=[1, 0.6, 2.5, 2.4]
    )
    
    # 二、旅程阶段划分
    add_title(doc, '二、旅程阶段划分', level=1)
    
    add_para(doc, '用户旅程分为6个主要阶段：发现阶段→注册阶段→首次使用→深度使用→留存阶段→推荐阶段。每个阶段包含用户行为、用户目标、用户痛点、情绪曲线、接触点、优化机会等维度。')
    
    add_table(doc,
        ['阶段', '时间范围', '用户状态', '核心目标'],
        [
            ['发现阶段', '首次接触产品前', '潜在用户', '了解产品，产生兴趣'],
            ['注册阶段', '首次访问到注册完成', '新用户', '快速注册，开始使用'],
            ['首次使用', '注册后第一次生成行程', '新用户', '成功生成第一个行程，体验产品价值'],
            ['深度使用', '使用1-4周', '活跃用户', '深入使用功能，生成多个行程'],
            ['留存阶段', '使用1-6个月', '核心用户', '持续使用，形成使用习惯'],
            ['推荐阶段', '使用6个月以上', '忠实用户', '推荐给他人，参与社区'],
        ],
        col_widths=[1, 1.5, 1.2, 2.8]
    )
    
    # 三、详细旅程地图
    add_title(doc, '三、详细旅程地图', level=1)
    
    add_title(doc, '3.1 发现阶段', level=2)
    
    add_title(doc, '3.1.1 用户行为', level=3)
    add_bullet(doc, '在小红书/抖音刷到旅行攻略或产品推荐')
    add_bullet(doc, '在知乎/百度搜索"旅行规划工具"、"AI行程生成"')
    add_bullet(doc, '朋友推荐或社群分享')
    add_bullet(doc, '应用商店搜索旅行相关App')
    add_bullet(doc, '点击链接访问产品官网或Web端')
    
    add_title(doc, '3.1.2 用户目标', level=3)
    add_bullet(doc, '了解产品是什么，能解决什么问题')
    add_bullet(doc, '判断产品是否适合自己')
    add_bullet(doc, '快速看到产品价值，产生使用欲望')
    
    add_title(doc, '3.1.3 用户痛点', level=3)
    add_bullet(doc, '旅行规划太麻烦，信息太多，不知道从何开始')
    add_bullet(doc, '传统规划工具太复杂，学习成本高')
    add_bullet(doc, 'OTA平台广告多，推荐不中立')
    add_bullet(doc, '攻略内容分散，需要自己整合')
    add_bullet(doc, '对AI产品有疑虑，不知道效果如何')
    
    add_title(doc, '3.1.4 情绪曲线', level=3)
    add_para(doc, '痛点（-2）→ 好奇（0）→ 期待（+1）→ 犹豫（0）')
    
    add_title(doc, '3.1.5 接触点', level=3)
    add_table(doc,
        ['接触点', '渠道', '内容', '优化方向'],
        [
            ['社交媒体', '小红书/抖音/视频号', '旅行攻略、产品演示、用户评价', '高质量内容、真实案例、清晰演示'],
            ['搜索引擎', '百度/知乎/微信搜一搜', '产品介绍、使用教程、对比评测', 'SEO优化、专业内容、口碑建设'],
            ['口碑传播', '朋友推荐/社群分享', '用户真实体验、行程分享', '激励分享、降低分享门槛'],
            ['应用商店', 'App Store/安卓应用商店', '产品介绍、截图、评价', 'ASO优化、精美截图、好评引导'],
            ['官网落地页', '产品官网', '产品介绍、功能演示、注册入口', '价值主张清晰、演示直观、注册简单'],
        ],
        col_widths=[1, 1.5, 2, 2]
    )
    
    add_title(doc, '3.1.6 优化机会', level=3)
    add_bullet(doc, '制作高质量的产品演示视频和GIF，直观展示产品价值')
    add_bullet(doc, '收集用户真实评价和行程案例，用于社交媒体传播')
    add_bullet(doc, '优化官网落地页，价值主张清晰，3秒内让用户理解产品')
    add_bullet(doc, '提供无需注册即可体验的Demo行程，降低试用门槛')
    add_bullet(doc, '与旅行KOL合作，产出真实使用体验内容')
    
    add_title(doc, '3.2 注册阶段', level=2)
    
    add_title(doc, '3.2.1 用户行为', level=3)
    add_bullet(doc, '访问产品首页，浏览产品介绍')
    add_bullet(doc, '点击注册/登录按钮')
    add_bullet(doc, '输入邮箱，获取验证码')
    add_bullet(doc, '输入验证码，完成注册')
    add_bullet(doc, '设置昵称、头像等个人信息（可选）')
    
    add_title(doc, '3.2.2 用户目标', level=3)
    add_bullet(doc, '快速完成注册，开始使用产品')
    add_bullet(doc, '注册流程简单，不繁琐')
    add_bullet(doc, '隐私安全有保障')
    
    add_title(doc, '3.2.3 用户痛点', level=3)
    add_bullet(doc, '注册流程太长，需要填写很多信息')
    add_bullet(doc, '需要设置复杂密码，容易忘记')
    add_bullet(doc, '担心隐私泄露，不想提供过多个人信息')
    add_bullet(doc, '验证码收不到或延迟')
    add_bullet(doc, '注册后不知道下一步做什么')
    
    add_title(doc, '3.2.4 情绪曲线', level=3)
    add_para(doc, '期待（+1）→ 焦虑（-1）→ 烦躁（-2）→ 释然（0）→ 迷茫（-1）')
    
    add_title(doc, '3.2.5 接触点', level=3)
    add_table(doc,
        ['接触点', '用户行为', '痛点', '优化方向'],
        [
            ['首页', '浏览产品介绍', '不知道产品能做什么', '价值主张清晰、Demo演示、用户评价'],
            ['注册页', '输入邮箱获取验证码', '流程复杂、验证码延迟', '简化流程、邮箱验证码、进度提示'],
            ['验证码', '输入验证码完成注册', '收不到验证码、输错', '60秒重发、错误提示、自动识别'],
            ['完善信息', '设置昵称头像', '不想填太多信息', '可选填写、跳过按钮、默认头像'],
            ['注册成功', '进入产品首页', '不知道下一步做什么', '新手引导、推荐目的地、示例行程'],
        ],
        col_widths=[1, 1.5, 1.8, 2.2]
    )
    
    add_title(doc, '3.2.6 优化机会', level=3)
    add_bullet(doc, '采用邮箱验证码注册，无需设置密码，降低注册门槛')
    add_bullet(doc, '注册流程控制在3步以内，每页只做一件事')
    add_bullet(doc, '提供"先体验后注册"模式，用户可先体验Demo行程再注册')
    add_bullet(doc, '注册成功后立即展示新手引导，推荐热门目的地')
    add_bullet(doc, '提供注册进度提示，让用户知道还有几步完成')
    add_bullet(doc, '验证码60秒可重发，提供语音验证码备选')
    
    add_title(doc, '3.3 首次使用', level=2)
    
    add_title(doc, '3.3.1 用户行为', level=3)
    add_bullet(doc, '进入对话首页，看到输入框和推荐目的地')
    add_bullet(doc, '输入旅行需求，如"我想去杭州玩3天"')
    add_bullet(doc, 'AI回复，可能引导补充参数（人数、预算等）')
    add_bullet(doc, '补充参数后，AI生成完整行程')
    add_bullet(doc, '查看行程详情（时间轴、地图、预算、预约提醒）')
    add_bullet(doc, '尝试调整行程（增减景点、修改天数）')
    add_bullet(doc, '分享行程或保存到历史行程')
    
    add_title(doc, '3.3.2 用户目标', level=3)
    add_bullet(doc, '成功生成第一个行程，体验产品核心价值')
    add_bullet(doc, '行程质量符合预期，景点合理，时间安排得当')
    add_bullet(doc, '操作简单，不需要学习就能使用')
    add_bullet(doc, '获得有用的信息，如预约提醒、避坑提示')
    
    add_title(doc, '3.3.3 用户痛点', level=3)
    add_bullet(doc, '不知道怎么输入，输入什么内容')
    add_bullet(doc, 'AI理解不准确，生成的行程不符合预期')
    add_bullet(doc, '行程景点太少或太多，时间安排不合理')
    add_bullet(doc, '生成时间太长，等待焦虑')
    add_bullet(doc, '行程展示不清晰，看不懂行程安排')
    add_bullet(doc, '调整行程不方便，修改后行程混乱')
    add_bullet(doc, '地图展示有问题，点位不准确')
    
    add_title(doc, '3.3.4 情绪曲线', level=3)
    add_para(doc, '好奇（0）→ 期待（+1）→ 焦虑（-1）→ 惊喜（+2）→ 失望（-2）→ 满意（+1）')
    
    add_title(doc, '3.3.5 关键指标', level=3)
    add_table(doc,
        ['指标', '定义', '目标值', '说明'],
        [
            ['首次行程生成率', '首次使用生成行程的用户/注册用户', '>80%', '核心转化指标'],
            ['首次生成时间', '从输入到生成行程的时间', '<4秒', '用户体验指标'],
            ['首次行程查看率', '查看行程详情的用户/生成行程用户', '>70%', '内容质量指标'],
            ['首次调整率', '调整行程的用户/查看行程用户', '>30%', '参与度指标'],
            ['首次分享率', '分享行程的用户/生成行程用户', '>10%', '传播指标'],
            ['次日留存率', '次日活跃用户/新增用户', '>40%', '留存指标'],
        ],
        col_widths=[1.5, 2.5, 1, 1.5]
    )
    
    add_title(doc, '3.3.6 优化机会', level=3)
    add_bullet(doc, '首页提供输入示例和推荐目的地，降低输入门槛')
    add_bullet(doc, '新手引导：首次使用时展示功能介绍和操作提示')
    add_bullet(doc, '优化AI理解能力，准确识别用户需求和参数')
    add_bullet(doc, '生成过程中展示进度和思考过程，减少等待焦虑')
    add_bullet(doc, '行程详情页设计清晰，时间轴+地图+预算+提醒一目了然')
    add_bullet(doc, '提供行程调整引导，告诉用户可以怎么调整')
    add_bullet(doc, '首次生成行程后，引导用户查看和分享')
    add_bullet(doc, '收集用户对行程的满意度反馈，持续优化')
    
    add_title(doc, '3.4 深度使用', level=2)
    
    add_title(doc, '3.4.1 用户行为', level=3)
    add_bullet(doc, '多次生成不同目的地的行程')
    add_bullet(doc, '使用探索功能，地图查看周边景点')
    add_bullet(doc, '查看景点人文介绍，了解历史文化')
    add_bullet(doc, '收藏喜欢的景点和行程')
    add_bullet(doc, '使用行程导出和分享功能')
    add_bullet(doc, '参与积分、签到、成就等运营活动')
    add_bullet(doc, '反馈问题和建议')
    
    add_title(doc, '3.4.2 用户目标', level=3)
    add_bullet(doc, '深入使用产品功能，提升旅行规划效率')
    add_bullet(doc, '发现更多有用的功能和内容')
    add_bullet(doc, '管理自己的行程和收藏')
    add_bullet(doc, '获得更多个性化推荐和服务')
    
    add_title(doc, '3.4.3 用户痛点', level=3)
    add_bullet(doc, '功能太多，不知道还有什么功能可以用')
    add_bullet(doc, '历史行程管理不方便，找不到之前的行程')
    add_bullet(doc, '推荐不够个性化，还是需要自己调整')
    add_bullet(doc, '景点信息不够全面，有些景点查不到')
    add_bullet(doc, '行程导出格式单一，不够精美')
    add_bullet(doc, '遇到问题找不到客服，反馈无回应')
    
    add_title(doc, '3.4.4 情绪曲线', level=3)
    add_para(doc, '满意（+1）→ 探索（0）→ 惊喜（+2）→ 平淡（0）→ 不满（-1）→ 忠诚（+2）')
    
    add_title(doc, '3.4.5 优化机会', level=3)
    add_bullet(doc, '功能发现：在合适的场景提示用户可用的功能，如生成行程后提示探索功能')
    add_bullet(doc, '历史行程：优化历史行程管理，支持搜索、分类、标签')
    add_bullet(doc, '个性化推荐：基于用户历史行程和偏好，推荐目的地和景点')
    add_bullet(doc, '内容扩充：持续扩充知识库，覆盖更多目的地和景点')
    add_bullet(doc, '导出优化：提供多种导出格式和精美模板')
    add_bullet(doc, '客服体系：建立多渠道客服，快速响应用户问题')
    add_bullet(doc, '用户反馈：建立反馈收集和处理机制，及时回应用户')
    add_bullet(doc, '会员体系：推出会员服务，提供更多高级功能和权益')
    
    add_title(doc, '3.5 留存阶段', level=2)
    
    add_title(doc, '3.5.1 用户行为', level=3)
    add_bullet(doc, '每次旅行前都使用产品规划行程')
    add_bullet(doc, '日常浏览旅行灵感和人文内容')
    add_bullet(doc, '参与社区互动，分享行程和攻略')
    add_bullet(doc, '购买会员，享受高级功能')
    add_bullet(doc, '推荐朋友使用产品')
    add_bullet(doc, '关注产品更新，参与内测')
    
    add_title(doc, '3.5.2 用户目标', level=3)
    add_bullet(doc, '产品成为旅行规划的首选工具')
    add_bullet(doc, '获得持续的价值和服务')
    add_bullet(doc, '参与社区，获得认同感和归属感')
    add_bullet(doc, '影响产品发展，参与共创')
    
    add_title(doc, '3.5.3 用户痛点', level=3)
    add_bullet(doc, '产品更新慢，新功能少')
    add_bullet(doc, '内容更新不及时，信息过时')
    add_bullet(doc, '社区氛围不好，广告多')
    add_bullet(doc, '会员权益不够，不值得续费')
    add_bullet(doc, '反馈的问题不被重视，不被采纳')
    add_bullet(doc, '竞品有更好的功能和体验')
    
    add_title(doc, '3.5.4 情绪曲线', level=3)
    add_para(doc, '忠诚（+2）→ 习惯（+1）→ 平淡（0）→ 期待（+1）→ 失望（-2）→ 流失（-3）')
    
    add_title(doc, '3.5.5 优化机会', level=3)
    add_bullet(doc, '持续迭代：保持产品更新频率，每月至少1次版本更新')
    add_bullet(doc, '内容更新：建立内容更新机制，及时更新景点信息和攻略')
    add_bullet(doc, '社区运营：建立健康的社区氛围，打击广告和垃圾内容')
    add_bullet(doc, '会员价值：持续增加会员权益，提升会员性价比')
    add_bullet(doc, '用户共创：邀请核心用户参与产品设计和内测，增强归属感')
    add_bullet(doc, '反馈闭环：建立反馈处理和公示机制，让用户看到自己的建议被采纳')
    add_bullet(doc, '流失预警：建立用户流失预警机制，及时召回可能流失的用户')
    add_bullet(doc, '竞品监控：持续关注竞品动态，及时跟进和超越')
    
    add_title(doc, '3.6 推荐阶段', level=2)
    
    add_title(doc, '3.6.1 用户行为', level=3)
    add_bullet(doc, '主动向朋友、同事推荐产品')
    add_bullet(doc, '在社交媒体分享行程和使用体验')
    add_bullet(doc, '在旅行社群推荐产品')
    add_bullet(doc, '撰写产品评测和使用教程')
    add_bullet(doc, '参与产品推广活动，邀请好友')
    
    add_title(doc, '3.6.2 用户目标', level=3)
    add_bullet(doc, '分享好产品，帮助他人')
    add_bullet(doc, '获得推荐奖励和认同感')
    add_bullet(doc, '建立自己在旅行领域的影响力')
    add_bullet(doc, '参与产品生态，获得更多权益')
    
    add_title(doc, '3.6.3 用户痛点', level=3)
    add_bullet(doc, '分享不方便，需要截图和复制链接')
    add_bullet(doc, '推荐奖励不够，没有动力推荐')
    add_bullet(doc, '朋友注册后体验不好，影响自己口碑')
    add_bullet(doc, '分享的行程不够精美，不想分享')
    add_bullet(doc, '没有推荐追踪，不知道推荐效果')
    
    add_title(doc, '3.6.4 优化机会', level=3)
    add_bullet(doc, '分享优化：一键分享到微信、朋友圈、小红书等平台')
    add_bullet(doc, '精美海报：生成精美的行程海报，便于分享和传播')
    add_bullet(doc, '推荐奖励：建立推荐奖励机制，推荐双方都获得奖励')
    add_bullet(doc, '推荐追踪：提供推荐数据看板，让用户看到推荐效果')
    add_bullet(doc, 'KOC培养：培养核心用户成为KOC，提供专属权益和支持')
    add_bullet(doc, '内容共创：邀请用户参与内容创作，获得收益分成')
    add_bullet(doc, '品牌大使：建立品牌大使计划，提供更多权益和曝光')
    
    # 四、痛点与机会汇总
    add_title(doc, '四、痛点与机会汇总', level=1)
    
    add_title(doc, '4.1 核心痛点汇总', level=2)
    add_table(doc,
        ['阶段', '核心痛点', '影响程度', '优先级'],
        [
            ['发现阶段', '对AI产品效果有疑虑，不知道是否好用', '高', 'P0'],
            ['发现阶段', '产品价值主张不清晰，不知道能解决什么问题', '高', 'P0'],
            ['注册阶段', '注册流程复杂，需要填写太多信息', '高', 'P0'],
            ['注册阶段', '注册后不知道下一步做什么', '中', 'P1'],
            ['首次使用', '不知道怎么输入，输入什么内容', '高', 'P0'],
            ['首次使用', 'AI理解不准确，生成的行程不符合预期', '高', 'P0'],
            ['首次使用', '生成时间太长，等待焦虑', '中', 'P1'],
            ['首次使用', '行程展示不清晰，看不懂安排', '中', 'P1'],
            ['深度使用', '功能太多，不知道还有什么功能', '中', 'P1'],
            ['深度使用', '历史行程管理不方便', '中', 'P1'],
            ['深度使用', '推荐不够个性化', '高', 'P0'],
            ['留存阶段', '产品更新慢，新功能少', '中', 'P1'],
            ['留存阶段', '内容更新不及时', '高', 'P0'],
            ['留存阶段', '会员权益不够', '中', 'P1'],
            ['推荐阶段', '分享不方便', '中', 'P1'],
            ['推荐阶段', '推荐奖励不够', '低', 'P2'],
        ],
        col_widths=[1, 3.5, 1, 1]
    )
    
    add_title(doc, '4.2 优化机会优先级', level=2)
    add_table(doc,
        ['优先级', '优化项', '预期效果', '实施难度'],
        [
            ['P0', '优化AI理解和行程生成质量', '提升核心体验，提高留存', '高'],
            ['P0', '清晰的产品价值主张和演示', '提升转化率，降低获客成本', '中'],
            ['P0', '简化注册流程，邮箱验证码', '提升注册转化率', '低'],
            ['P0', '首页输入引导和推荐目的地', '提升首次使用率', '低'],
            ['P0', '持续更新知识库内容', '提升内容质量，用户信任', '中'],
            ['P1', '生成过程进度展示', '降低等待焦虑', '中'],
            ['P1', '行程详情页信息架构优化', '提升可读性和易用性', '中'],
            ['P1', '功能发现和新手引导', '提升功能使用率', '中'],
            ['P1', '历史行程管理优化', '提升用户效率', '中'],
            ['P1', '个性化推荐算法', '提升用户粘性', '高'],
            ['P1', '产品持续迭代机制', '提升用户留存', '中'],
            ['P2', '精美行程海报和分享', '提升传播率', '中'],
            ['P2', '推荐奖励机制', '提升裂变增长', '中'],
            ['P2', '会员体系和权益', '提升商业化收入', '中'],
        ],
        col_widths=[0.6, 2.5, 2, 1.4]
    )
    
    # 五、用户体验优化建议
    add_title(doc, '五、用户体验优化建议', level=1)
    
    add_title(doc, '5.1 新手体验优化', level=2)
    add_bullet(doc, '首次访问展示产品价值演示，30秒视频或GIF')
    add_bullet(doc, '提供"体验Demo"按钮，无需注册即可查看示例行程')
    add_bullet(doc, '注册后立即展示新手引导，3步完成首次行程生成')
    add_bullet(doc, '首页提供热门目的地推荐和输入示例')
    add_bullet(doc, '首次生成行程后，引导用户查看详情和调整行程')
    add_bullet(doc, '收集首次使用反馈，及时优化问题')
    
    add_title(doc, '5.2 对话体验优化', level=2)
    add_bullet(doc, '输入框提供智能提示，根据输入内容推荐可能的需求')
    add_bullet(doc, 'AI回复采用流式输出，减少等待感')
    add_bullet(doc, '生成行程时展示思考过程，如"正在分析需求"、"正在检索景点"')
    add_bullet(doc, '参数缺失时主动引导，提供选项按钮，减少用户输入')
    add_bullet(doc, '支持快捷操作，如"调整天数"、"增加景点"、"重新生成"')
    add_bullet(doc, '对话历史时间线展示，支持下拉加载更多')
    
    add_title(doc, '5.3 行程展示优化', level=2)
    add_bullet(doc, '时间轴+地图双视图，可切换查看')
    add_bullet(doc, '每日行程卡片化，景点、交通、餐饮清晰区分')
    add_bullet(doc, '预约提醒在顶部醒目展示，可点击查看详情')
    add_bullet(doc, '避坑提示穿插在对应景点下方，关联展示')
    add_bullet(doc, '预算明细可展开查看，分类清晰')
    add_bullet(doc, '提供行程概览和详细视图切换')
    
    add_title(doc, '5.4 留存机制优化', level=2)
    add_bullet(doc, '建立用户成长体系，等级、成就、徽章')
    add_bullet(doc, '每日签到和任务系统，提升日活')
    add_bullet(doc, '个性化旅行灵感推送，激发出行欲望')
    add_bullet(doc, '节日和旅行季活动，提升活跃度')
    add_bullet(doc, '用户反馈闭环，让用户看到建议被采纳')
    add_bullet(doc, '会员专属权益，提升付费转化和留存')
    
    # 六、总结
    add_title(doc, '六、总结', level=1)
    
    add_para(doc, '通过对用户旅程的全面梳理，可以看出：')
    
    add_bullet(doc, '核心转化路径：发现→注册→首次使用→留存→推荐，每个环节都有明确的优化空间')
    add_bullet(doc, '最关键阶段：首次使用是用户体验的核心，行程生成质量决定用户是否留存')
    add_bullet(doc, '最大痛点：AI理解不准确、行程生成质量不稳定、内容更新不及时')
    add_bullet(doc, '最高优先级：优化AI理解和行程生成质量，是产品的核心竞争力')
    add_bullet(doc, '增长机会：通过精美分享和推荐奖励，实现裂变增长')
    
    add_para(doc, '建议以用户旅程地图为指导，按优先级逐步优化各阶段体验，重点关注首次使用和行程质量，建立良好的用户口碑，实现可持续增长。')
    
    output_path = os.path.join(OUTPUT_DIR, '05_用户旅程地图.docx')
    doc.save(output_path)
    print(f'已生成: {output_path}')
    return output_path


# ============================================================
# 主函数
# ============================================================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print('开始生成5份Word文档...')
    print('=' * 50)
    
    paths = []
    paths.append(generate_prd())
    paths.append(generate_operation_plan())
    paths.append(generate_business_plan())
    paths.append(generate_competitor_analysis())
    paths.append(generate_user_journey())
    
    print('=' * 50)
    print('全部文档生成完成！')
    print(f'输出目录: {OUTPUT_DIR}')
    print('\n文件列表:')
    for i, path in enumerate(paths, 1):
        size = os.path.getsize(path) / 1024
        print(f'  {i}. {os.path.basename(path)} ({size:.1f} KB)')

if __name__ == '__main__':
    main()
