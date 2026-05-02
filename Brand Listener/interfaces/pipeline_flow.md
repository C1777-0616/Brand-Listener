# LangGraph MVP - 代理工作流草案

- 4 大组分工：Searcher、Analyst、Reporter、Supervisor。
- 每组含若干子代理，输入输出通过统一契约对接，数据以 Mock 为主，后续替换为真实数据源。
- 数据流示意：Supervisor 定义任务并触发数据采集；Searcher 收集并规范化数据，Analyst 进行分析，Reporter 生成报告，Supervisor 监控执行与导出。

注：此文档用于设计对接点，后续阶段将逐步细化为正式实现细节。
