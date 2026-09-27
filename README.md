# 设计竞赛检索与规则解析 Agent

[在线体验](https://feyzha-design-scout.vercel.app) · [GitHub](https://github.com/FeyZha/design-competition-agent)

发现设计竞赛，将分散的网页及附件规则整理成可追溯的投稿方向与创作任务书。

## 功能

- 保存赛事规则，区分独立投稿方向、可选类别与绑定交付材料。
- 通过预制对话查看竞赛推荐、资格、费用、截止时间及 AI 规则。
- 保留来源引用、待确认信息与旧结果，避免不完整提取覆盖已有资料。
- 下载所选方向的任务书。

## 在线演示

Demo 内置 106 条已保存赛事及待整理记录，沿用原项目的对话式界面，提供海报推荐、规则解析、绑定交付核对和无匹配四种预制对话场景。只能点击预制问题，不开放自由输入；回复与结果固定于 2026-09-22 的快照。数据是历史快照，不代表当前可报名；公开版不抓取新赛事、不调用大模型、不提供 API 配置。

## 快速开始

```sh
cd demo
npm ci
npm run dev
```

## 构建与测试

```sh
cd demo
npm test
npm run build
```

需要 Node.js 22.13 或更高版本。Vercel 可直接读取根目录 `vercel.json` 部署。

## 项目结构

- `agent/`：原竞赛发现、网页/附件读取、规则提取与校验实现，附 Python 回归检查。
- `demo/src/competition-results.ts`：复用的方向整理与匹配规则。
- `demo/src/competition-brief.ts`：任务书内容处理。
- `demo/public/feed.json`：预制赛事快照及来源。

## 原理

赛事发现 → 网页与附件读取 → 结构化提取 → 来源与完整性校验 → 按投稿方向筛选 → 确认创作类别 → 任务书。

## 来源与许可

此模块从基于 [basketikun/infinite-canvas](https://github.com/basketikun/infinite-canvas) 的本地工作台独立提取，保留上游 MIT 许可。公开 Demo 不包含画布生成能力。赛事规则来自所标注的网站，其权利属于原发布者；报名前应核实官方最新规则。
