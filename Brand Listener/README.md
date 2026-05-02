# Brand Listener — LangGraph MVP 架构骨架

说明：本项目在 Brand Listener 顶级目录下建立主架构与接口占位，四大代理组（Searcher、Analyst、Reporter、Supervisor）及其子代理的入口均已创建占位文件与契约。后续将逐步按照 Phase 1~Phase 8 的计划实现具体的 Agents 与数据对接。当前阶段强调框架、接口契约、Mock 数据路径与导出入口的占位。

文件结构要点：
- frontend: 前端 UI 框架骨架，供后续对接数据流演示
- langgraph: 顶层架构（骨架）
- agents: 四大组及子代理的入口 YAML/JSON 占位
- data/mock: Mock 数据及数据结构说明
- config: 配置与契约文档占位

未来工作：按阶段实现各 Agent 的具体行为、数据对接、PDF 输出与外部系统对接等功能。
