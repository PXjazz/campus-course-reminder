import streamlit as st
import pandas as pd
import datetime
from typing import Optional

# -------------------------- 页面配置 --------------------------
st.set_page_config(
    page_title="校园课程表智能提醒",
    page_icon="📚",
    layout="wide"
)

# -------------------------- 初始化会话状态 --------------------------
if "course_data" not in st.session_state:
    st.session_state.course_data = None  # 课程表数据
if "remind_minutes" not in st.session_state:
    st.session_state.remind_minutes = 10  # 默认提前10分钟提醒
if "adjust_courses" not in st.session_state:
    st.session_state.adjust_courses = []  # 调课信息
if "current_remind" not in st.session_state:
    st.session_state.current_remind = None  # 当前提醒的课程
if "semester_start" not in st.session_state:
    st.session_state.semester_start = "2025-09-01"  # 默认开学时间

# -------------------------- 辅助函数 --------------------------
def parse_course_time(time_str: str) -> datetime.time:
    """解析时间字符串（如08:00）为datetime.time对象"""
    try:
        return datetime.datetime.strptime(time_str, "%H:%M").time()
    except:
        st.error(f"时间格式错误：{time_str}，请使用HH:MM格式（如08:00）")
        return datetime.time(0, 0)

def get_week_num() -> int:
    """获取当前学期第几周（支持自定义开学时间）"""
    try:
        start_date = datetime.datetime.strptime(st.session_state.semester_start, "%Y-%m-%d")
        today = datetime.datetime.now()
        if today < start_date:
            return 0
        week_num = (today - start_date).days // 7 + 1
        return week_num
    except Exception as e:
        st.warning(f"开学时间解析失败，默认显示第1周：{e}")
        return 1

def check_week_range(week_str: Optional[str], current_week: int) -> bool:
    """检查当前周是否在课程周次范围内（如1-16周、3,5,7周）"""
    if pd.isna(week_str) or week_str == "":
        return True  # 无周次限制则默认显示
    # 处理区间格式（1-16）
    if "-" in week_str:
        try:
            start_week, end_week = map(int, week_str.split("-"))
            return start_week <= current_week <= end_week
        except:
            return False
    # 处理逗号分隔（3,5,7）
    elif "," in week_str:
        try:
            week_list = list(map(int, week_str.split(",")))
            return current_week in week_list
        except:
            return False
    # 单周（8）
    else:
        try:
            return int(week_str) == current_week
        except:
            return False

def get_today_courses() -> pd.DataFrame:
    """获取今日课程（含调课）"""
    if st.session_state.course_data is None:
        return pd.DataFrame()
    
    # 获取今日星期（1=周一，7=周日）
    today_weekday = datetime.datetime.now().isoweekday()
    current_week = get_week_num()
    
    # 筛选今日课程
    today_courses = st.session_state.course_data[
        (st.session_state.course_data["星期"] == today_weekday) &
        st.session_state.course_data["周次"].apply(lambda x: check_week_range(x, current_week))
    ].copy()
    
    # 合并调课信息
    for adjust in st.session_state.adjust_courses:
        if adjust["星期"] == today_weekday and check_week_range(adjust["周次"], current_week):
            # 替换原课程或添加新课程
            mask = (today_courses["开始时间"] == adjust["原开始时间"]) & (today_courses["课程名称"] == adjust["原课程名"])
            if mask.any():
                today_courses.loc[mask, ["课程名称", "地点", "教师", "开始时间", "结束时间"]] = [
                    adjust["新课程名"], adjust["新地点"], adjust["新教师"], adjust["新开始时间"], adjust["新结束时间"]
                ]
            else:
                new_course = pd.DataFrame([{
                    "星期": adjust["星期"],
                    "开始时间": adjust["新开始时间"],
                    "结束时间": adjust["新结束时间"],
                    "课程名称": adjust["新课程名"],
                    "地点": adjust["新地点"],
                    "教师": adjust["新教师"],
                    "周次": adjust["周次"]
                }])
                today_courses = pd.concat([today_courses, new_course], ignore_index=True)
    
    # 按开始时间排序
    today_courses["开始时间_obj"] = today_courses["开始时间"].apply(parse_course_time)
    today_courses = today_courses.sort_values("开始时间_obj").drop("开始时间_obj", axis=1)
    return today_courses

def check_remind() -> None:
    """检查是否需要提醒课程（适配云端）"""
    today_courses = get_today_courses()
    if today_courses.empty:
        st.session_state.current_remind = None
        return
    
    now = datetime.datetime.now()
    remind_time = now + datetime.timedelta(minutes=st.session_state.remind_minutes)
    
    for _, course in today_courses.iterrows():
        # 解析课程时间
        course_start = datetime.datetime.combine(now.date(), parse_course_time(course["开始时间"]))
        # 检查是否在提醒时间段内
        if now <= course_start <= remind_time:
            st.session_state.current_remind = course
            return
    
    st.session_state.current_remind = None

# -------------------------- 界面设计 --------------------------
st.title("📚 校园课程表智能提醒工具")
st.divider()

# 侧边栏
with st.sidebar:
    st.header("⚙️ 基础设置")
    
    # 1. 开学时间配置
    st.subheader("📅 学期设置")
    semester_start = st.date_input(
        "选择开学日期",
        value=datetime.datetime.strptime(st.session_state.semester_start, "%Y-%m-%d").date(),
        key="semester_start_picker"
    )
    st.session_state.semester_start = semester_start.strftime("%Y-%m-%d")
    
    # 2. 上传课程表
    st.subheader("📤 导入课程表")
    st.markdown("""
    ### 模板格式（Excel列）：
    - 星期（1=周一，7=周日）
    - 开始时间（如08:00）
    - 结束时间（如08:45）
    - 课程名称
    - 地点
    - 教师
    - 周次（如1-16或3,5,7）
    """)
    uploaded_file = st.file_uploader("上传Excel课程表", type=["xlsx"])
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            # 检查必要列
            required_cols = ["星期", "开始时间", "结束时间", "课程名称", "地点", "教师", "周次"]
            if all(col in df.columns for col in required_cols):
                # 数据类型转换与清洗
                df["星期"] = pd.to_numeric(df["星期"], errors="coerce").fillna(0).astype(int)
                df = df[df["星期"] >= 1 & df["星期"] <= 7]  # 过滤无效星期
                st.session_state.course_data = df
                st.success("✅ 课程表导入成功！")
            else:
                st.error(f"❌ 缺少必要列，需包含：{required_cols}")
        except Exception as e:
            st.error(f"❌ 导入失败：{str(e)}")
    
    # 3. 提醒时间设置
    st.subheader("⏰ 提醒设置")
    remind_min = st.selectbox(
        "提前提醒时间（分钟）", 
        [5, 10, 15, 20], 
        index=st.session_state.remind_minutes//5 - 1,
        key="remind_min_select"
    )
    st.session_state.remind_minutes = remind_min
    
    # 4. 调课信息录入
    st.subheader("📝 调课管理")
    with st.form("adjust_form", clear_on_submit=True):
        adjust_week = st.number_input("星期（1=周一）", min_value=1, max_value=7, value=1, key="adjust_week")
        adjust_week_str = st.text_input("周次（如1-16）", value="1-16", key="adjust_week_str")
        original_course = st.text_input("原课程名称", key="original_course")
        original_start = st.text_input("原开始时间（如08:00）", key="original_start")
        new_course = st.text_input("新课程名称", key="new_course")
        new_start = st.text_input("新开始时间（如09:00）", key="new_start")
        new_end = st.text_input("新结束时间（如09:45）", key="new_end")
        new_place = st.text_input("新地点", key="new_place")
        new_teacher = st.text_input("新教师", key="new_teacher")
        submit_adjust = st.form_submit_button("添加调课信息")
        
        if submit_adjust:
            if not all([original_course, original_start, new_course, new_start, new_end]):
                st.error("❌ 请填写必填项（原课程名、原开始时间、新课程名、新开始/结束时间）")
            else:
                st.session_state.adjust_courses.append({
                    "星期": adjust_week,
                    "周次": adjust_week_str,
                    "原课程名": original_course,
                    "原开始时间": original_start,
                    "新课程名": new_course,
                    "新开始时间": new_start,
                    "新结束时间": new_end,
                    "新地点": new_place,
                    "新教师": new_teacher
                })
                st.success("✅ 调课信息添加成功！")
    
    # 显示并删除调课信息
    if st.session_state.adjust_courses:
        st.subheader("当前调课列表")
        for i, adjust in enumerate(st.session_state.adjust_courses):
            col_adjust, col_del = st.columns([4, 1])
            with col_adjust:
                st.write(f"{i+1}. {adjust['原课程名']} → {adjust['新课程名']}（周{adjust['星期']} {adjust['新开始时间']}）")
            with col_del:
                if st.button("删除", key=f"del_{i}"):
                    st.session_state.adjust_courses.pop(i)
                    st.rerun()

# 主界面
col1, col2 = st.columns([2, 1])

with col1:
    # 今日课程
    st.header("📅 今日课程")
    today_courses = get_today_courses()
    if not today_courses.empty:
        # 美化表格显示
        st.dataframe(
            today_courses.drop(["星期", "周次"], axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "开始时间": st.column_config.TextColumn("开始时间", width="small"),
                "结束时间": st.column_config.TextColumn("结束时间", width="small"),
                "课程名称": st.column_config.TextColumn("课程名称", width="medium"),
                "地点": st.column_config.TextColumn("地点", width="small"),
                "教师": st.column_config.TextColumn("教师", width="small")
            }
        )
    else:
        st.info("🎉 今日无课程，好好休息！")
    
    # 本周课程概览
    st.header("📖 本周课程概览")
    if st.session_state.course_data is not None:
        current_week = get_week_num()
        week_courses = st.session_state.course_data[
            st.session_state.course_data["周次"].apply(lambda x: check_week_range(x, current_week))
        ].copy()
        
        if not week_courses.empty:
            # 按星期和时间排序
            week_courses["开始时间_obj"] = week_courses["开始时间"].apply(parse_course_time)
            week_courses = week_courses.sort_values(["星期", "开始时间_obj"]).drop("开始时间_obj", axis=1)
            
            # 按星期分组显示
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            for weekday in range(1, 8):
                weekday_courses = week_courses[week_courses["星期"] == weekday]
                if not weekday_courses.empty:
                    with st.expander(f"{weekday_names[weekday-1]}"):
                        st.dataframe(
                            weekday_courses.drop(["星期", "周次"], axis=1),
                            use_container_width=True,
                            hide_index=True
                        )
        else:
            st.info("本周无课程安排")
    else:
        st.warning("⚠️ 请先上传课程表！")

with col2:
    # 实时提醒区域
    st.header("🚨 实时提醒")
    now = datetime.datetime.now()
    st.metric("当前时间", now.strftime("%Y-%m-%d %H:%M:%S"))
    st.metric("当前学期周数", get_week_num())
    st.metric("提前提醒时间", f"{st.session_state.remind_minutes} 分钟")
    
    st.divider()
    
    # 触发提醒检查
    check_remind()
    
    # 显示当前提醒
    if st.session_state.current_remind is not None:
        course = st.session_state.current_remind
        st.error(f"""
        ⚠️ 即将上课！
        ├─ 课程名称：{course['课程名称']}
        ├─ 上课时间：{course['开始时间']}-{course['结束时间']}
        ├─ 上课地点：{course['地点']}
        └─ 授课教师：{course['教师']}
        """)
        # 提醒音效（可选，需浏览器允许自动播放）
        try:
            st.audio("https://assets.mixkit.co/sfx/preview/mixkit-alarm-digital-clock-beep-989.mp3", autoplay=True)
        except:
            st.warning("提醒音效加载失败")
    else:
        st.success("✅ 暂无待提醒课程")
    
    # 手动刷新按钮
    if st.button("🔄 刷新提醒状态"):
        check_remind()
        st.rerun()

# 页脚
st.divider()
st.markdown("""
    <style>
    .footer {text-align: center; color: #666; margin-top: 20px; font-size: 0.9em;}
    </style>
    <div class="footer">
        校园课程表智能提醒工具 | 基于Streamlit开发 | 部署于Streamlit Community Cloud
    </div>
""", unsafe_allow_html=True)

# 自动刷新（每30秒刷新页面，保持提醒实时）
st.markdown("""
    <meta http-equiv="refresh" content="30">
""", unsafe_allow_html=True)
