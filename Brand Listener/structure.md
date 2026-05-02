Brand Listener 架构 - 规范化目录结构

目标：将历史重复路径清理为一个单一、清晰的根目录结构，便于后续开发按阶段推进。

推荐的规范根路径（Brand Listener 顶层）
- Brand Listener/frontend: 前端骨架与静态页面
- Brand Listener/langgraph: LangGraph 顶层架构定义
- Brand Listener/agents: 四大组及子代理的入口文件夹
  - Brand Listener/agents/searcher
  - Brand Listener/agents/analyst
  - Brand Listener/agents/reporter
  - Brand Listener/agents/supervisor
- Brand Listener/data/mock: Mock 数据与数据模型示例
- Brand Listener/config: 配置与契约占位
- Brand Listener/interfaces: 数据契约入口（JSON/MD 文档）
- Brand Listener/README.md: 项目标注与使用说明

备注：当前阶段优先建立框架与接口契约，模板定义、PDF 输出和对外系统对接留待后续阶段实现。
