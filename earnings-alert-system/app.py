from __future__ import annotations

import json

import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf

from config import load_config
from main import run_scan
from src.database import DatabaseManager
from src.utils import get_logger, normalize_yahoo_symbol


logger = get_logger(__name__)


st.set_page_config(page_title="美股财报异动预警系统", layout="wide")


@st.cache_resource
def get_database() -> DatabaseManager:
    config = load_config()
    database = DatabaseManager(config)
    database.init_db()
    return database


def load_watchlist(selected_date: str | None = None, priority: str | None = None) -> pd.DataFrame:
    database = get_database()
    run_date = selected_date
    if run_date is None:
        dates = database.available_watchlist_dates()
        run_date = dates[0] if dates else None
    return database.fetch_watchlist(run_date=run_date, priority=priority)


@st.cache_data(ttl=300, show_spinner=False)
def load_symbol_accuracies() -> dict:
    database = get_database()
    return database.get_symbol_accuracies()


@st.cache_data(ttl=1800, show_spinner=False)
def load_price_chart_data(symbol: str) -> pd.DataFrame:
    yf_symbol = normalize_yahoo_symbol(symbol)
    try:
        history = yf.Ticker(yf_symbol).history(period="1mo")
    except Exception as exc:
        logger.warning("Failed to load chart data for %s (%s): %s", symbol, yf_symbol, exc)
        return pd.DataFrame()
    if history.empty:
        return pd.DataFrame()

    chart_df = history.reset_index()[["Date", "Close"]].copy()
    chart_df["Date"] = pd.to_datetime(chart_df["Date"]).dt.tz_localize(None)
    chart_df = chart_df.rename(columns={"Date": "日期", "Close": "收盘价"})
    return chart_df


def render_empty_state(has_history: bool) -> None:
    if not has_history:
        st.info(
            "当前还没有扫描结果。财报日历已改为 Nasdaq 公开接口，无需配置 API Key；"
            "请先点击左侧“刷新数据”执行一次扫描。"
        )
        st.caption("OPENAI_API_KEY 和 FINNHUB_API_KEY 都是增强项，不是启动或刷出基础榜单的前提。")
        return

    st.warning("本次筛选条件下暂无结果。你可以切换扫描日期、优先级，或重新点击“刷新数据”。")


def render_item(row: pd.Series, accuracies: dict) -> None:
    reasons = _parse_list(row.get("reasons"))
    risks = _parse_list(row.get("risks"))
    chart_df = load_price_chart_data(row["symbol"])
    acc = accuracies.get(row["symbol"])

    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])
        col1.metric("股票代码", row["symbol"])
        col2.write(f"**{row['company_name']}**")
        col2.caption(f"财报日期：{row['earnings_date']} | 公布时间：{row['earnings_time']}")
        col3.metric("综合评分", int(row["total_score"]))
        col4.metric("优先级", row["priority"])
        if acc and acc["total"] > 0:
            label = f"{acc['accuracy_pct']}%（{acc['correct']}/{acc['total']}次）"
            col5.metric("历史准确率", label, delta="优先推荐" if acc["accuracy_pct"] > 60 else None)
        else:
            col5.metric("历史准确率", "暂无记录")

        details_col, chart_col = st.columns([1.3, 1])

        with details_col:
            st.write("**核心原因**")
            if reasons:
                for reason in reasons:
                    st.write(f"- {reason}")
            else:
                st.write("- 暂无明确加分原因")

            st.write("**风险提示**")
            if risks:
                for risk in risks:
                    st.write(f"- {risk}")
            else:
                st.write("- 暂无明显风险提示")

        with chart_col:
            st.write("**近 1 个月股价**")
            if chart_df.empty:
                st.caption("暂无可用价格数据")
            else:
                chart = (
                    alt.Chart(chart_df)
                    .mark_area(
                        line={"color": "#1f77b4", "strokeWidth": 1.5},
                        color=alt.Gradient(
                            gradient="linear",
                            stops=[
                                alt.GradientStop(color="#1f77b4", offset=0),
                                alt.GradientStop(color="white", offset=1),
                            ],
                            x1=1, x2=1, y1=1, y2=0,
                        ),
                    )
                    .encode(
                        x=alt.X("日期:T", axis=alt.Axis(format="%m/%d", labelAngle=-30, title=None)),
                        y=alt.Y(
                            "收盘价:Q",
                            scale=alt.Scale(zero=False, padding=10),
                            axis=alt.Axis(title=None, format=",.0f"),
                        ),
                        tooltip=[
                            alt.Tooltip("日期:T", title="日期", format="%Y-%m-%d"),
                            alt.Tooltip("收盘价:Q", title="收盘价", format=",.2f"),
                        ],
                    )
                    .properties(height=240)
                )
                st.altair_chart(chart, use_container_width=True)


def _parse_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []


def main() -> None:
    st.title("美股财报异动预警系统")
    st.caption("扫描近期将发布财报的美股公司，结合价格、新闻和分析师信号生成关注名单。")

    database = get_database()
    if "scan_message" not in st.session_state:
        st.session_state["scan_message"] = ""

    available_dates = database.available_watchlist_dates()

    with st.sidebar:
        st.header("控制面板")
        with st.form("scan_form", clear_on_submit=False):
            days = st.slider("扫描未来财报天数", min_value=7, max_value=14, value=7)
            st.caption("默认会过滤小市值股票，并限制单次扫描数量，以缩短刷新时间。")
            refresh = st.form_submit_button("刷新数据", type="primary")

        st.divider()
        st.caption("以下选项只筛选当前已生成的结果，不会重新扫描。")
        selected_priority = st.selectbox("优先级筛选", ["全部", "高", "中", "低"])
        selected_date = st.selectbox("扫描日期", ["最新"] + available_dates if available_dates else ["最新"])

    if refresh:
        with st.spinner("正在刷新数据，请稍候..."):
            frame = run_scan(days=days)
        st.session_state["scan_message"] = f"刷新完成，共生成 {len(frame)} 条结果。"
        available_dates = database.available_watchlist_dates()
    elif st.session_state["scan_message"]:
        st.success(st.session_state["scan_message"])

    query_date = None if selected_date == "最新" else selected_date
    query_priority = None if selected_priority == "全部" else selected_priority
    frame = load_watchlist(selected_date=query_date, priority=query_priority)

    if frame.empty:
        render_empty_state(has_history=bool(available_dates))
        return

    accuracies = load_symbol_accuracies()
    frame["历史准确率"] = frame["symbol"].map(
        lambda s: accuracies[s]["accuracy_pct"] if s in accuracies else None
    )
    frame["_good_accuracy"] = frame["历史准确率"].apply(lambda x: x is not None and x > 60)
    frame = frame.sort_values(
        by=["_good_accuracy", "total_score", "earnings_date"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    frame = frame.drop(columns=["_good_accuracy"])

    st.subheader("今日关注榜")
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("股票数量", len(frame))
    metric_col2.metric("高优先级", int((frame["priority"] == "高").sum()))
    metric_col3.metric("平均得分", round(frame["total_score"].mean(), 1))

    export_df = frame[["symbol", "company_name", "earnings_date", "earnings_time", "total_score", "priority", "历史准确率"]]
    st.download_button(
        label="导出 CSV",
        data=export_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="earnings_watchlist.csv",
        mime="text/csv",
    )

    st.dataframe(export_df, use_container_width=True, hide_index=True)

    accuracies = load_symbol_accuracies()

    good_acc_count = int(frame["历史准确率"].apply(lambda x: x is not None and x > 60).sum())
    if good_acc_count:
        st.info(f"其中 **{good_acc_count}** 只股票历史预测准确率 > 60%，已排在前列。")

    st.subheader("个股详情")
    for _, row in frame.iterrows():
        render_item(row, accuracies)


if __name__ == "__main__":
    main()
