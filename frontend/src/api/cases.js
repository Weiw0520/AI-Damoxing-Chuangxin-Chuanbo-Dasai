import { MOCK_CASES } from './fixtures'
// Input presets only. Generation always goes through POST /api/drafts.
export const CASES = [{
  id: 'yangjiabu', no: '01', label: '杨家埠木版年画', caseType: '杨家埠联调',
  hint: '两份独立资料 · 保留原文与链接', platform: '小红书',
  requirement: '写一篇面向年轻游客的小红书文案，介绍杨家埠木版年画来自哪里、是怎么做出来的。',
  sources: [
    { title: '杨家埠木版年画｜国家级非遗项目介绍', text: '山东省潍坊市杨家埠的一种民间版画', url: 'https://www.ihchina.cn/project_details/13904.html' },
    { title: '年画之乡景色新｜工艺介绍', text: '杨家埠木版年画分钩描、刻版、印刷3道工序', url: 'https://www.ihchina.cn/project_details/9691' },
  ],
}, ...MOCK_CASES.map((c, index) => ({
  id: c.id, no: String(index + 2).padStart(2, '0'), label: c.label,
  caseType: c.caseType, hint: '示例资料节选 · 结果以 C 返回为准', requirement: c.requirement, platform: '小红书',
  sources: c.result.sources.map((s) => ({ title: s.title, text: s.snippet, url: s.url || '' })),
}))]
