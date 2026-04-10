import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "cotodo",
  description: "Async human-AI collaboration via shared TODO.md",
  base: process.env.VITEPRESS_BASE || "/",
  lastUpdated: true,

  locales: {
    root: {
      label: 'English',
      lang: 'en',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/' },
          { text: 'Guide', link: '/guide/overview' }
        ],
        sidebar: [
          {
            text: 'Guide',
            items: [
              { text: 'Overview', link: '/guide/overview' },
              { text: 'Protocol', link: '/guide/protocol' },
              { text: 'Agent Behavior', link: '/guide/agent-behavior' }
            ]
          }
        ]
      }
    },
    zh: {
      label: '简体中文',
      lang: 'zh-CN',
      themeConfig: {
        nav: [
          { text: '首页', link: '/zh/' },
          { text: '指南', link: '/zh/guide/overview' }
        ],
        sidebar: [
          {
            text: '指引',
            items: [
              { text: '概览', link: '/zh/guide/overview' },
              { text: '协议', link: '/zh/guide/protocol' },
              { text: 'Agent 行为规则', link: '/zh/guide/agent-behavior' }
            ]
          }
        ]
      }
    }
  },

  themeConfig: {
    teekHome: false,
    vpHome: true,
    search: { provider: "local" },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/HoG-ai/cotodo' }
    ]
  }
})
