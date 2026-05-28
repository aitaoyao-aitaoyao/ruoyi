/**
 * LightPress CMS — Vue 3 单页应用 (SPA)
 *
 * 架构说明:
 *   - 使用 Vue 3 CDN 版（无需构建工具，直接通过 <script> 加载）
 *   - 哈希路由 (#/dashboard, #/articles 等) 实现页面切换，无需后端配置
 *   - JWT Token 存储在 localStorage，每次请求通过 Authorization 头携带
 *   - API 辅助对象封装了 fetch，自动附加 Token、统一错误处理
 *
 * 组件树:
 *   App (根组件)
 *   ├── LoginForm         登录/注册表单（未登录时显示）
 *   ├── Sidebar           侧边栏导航（已登录时显示）
 *   ├── Dashboard         仪表盘（统计卡片 + 最近文章 + 快捷操作）
 *   ├── ArticleList       文章列表（筛选 + 表格 + 工作流操作）
 *   ├── ArticleEditor     文章编辑器（创建/编辑 + 保存草稿 + 提交审核）
 *   ├── MediaLibrary      媒体库（文件上传 + 网格展示 + 删除）
 *   ├── CategoryManager   分类管理（增删查）
 *   ├── TagManager        标签管理（增删查 + 文章数统计）
 *   └── UserManager       用户管理（仅管理员可见）
 */

// ======================== API 请求封装 ========================

const API = {
  base: '',  // API 基础路径，空字符串表示同域请求

  // 从 localStorage 读取 JWT Token
  token() { return localStorage.getItem('token'); },

  // 构建请求头：JSON 类型 + Bearer Token（如果已登录）
  headers(extra) {
    const h = { 'Content-Type': 'application/json', ...extra };
    if (this.token()) h['Authorization'] = `Bearer ${this.token()}`;
    return h;
  },

  // GET 请求
  async get(url) {
    const r = await fetch(this.base + url, { headers: this.headers() });
    return r.status === 204 ? null : r.json();
  },

  // POST 请求（JSON body）
  async post(url, data) {
    const r = await fetch(this.base + url, {
      method: 'POST', headers: this.headers(), body: JSON.stringify(data)
    });
    if (r.status === 204) return null;
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || '请求失败');
    return j;
  },

  // PATCH 请求（部分更新）
  async patch(url, data) {
    const r = await fetch(this.base + url, {
      method: 'PATCH', headers: this.headers(), body: JSON.stringify(data)
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || '请求失败');
    return j;
  },

  // DELETE 请求
  async delete(url) {
    const r = await fetch(this.base + url, {
      method: 'DELETE', headers: this.headers()
    });
    if (!r.ok && r.status !== 204) {
      const j = await r.json(); throw new Error(j.detail || '删除失败');
    }
  },

  // 文件上传（multipart/form-data，不设 Content-Type 让浏览器自动处理）
  async upload(url, formData) {
    const r = await fetch(this.base + url, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${this.token()}` },
      body: formData,
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || '上传失败');
    return j;
  },
};

// ======================== Vue 应用初始化 ========================

const { createApp } = Vue;

// ======================== 登录/注册组件 ========================

const LoginForm = {
  template: `
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-blue-400">LightPress</h1>
        <p class="text-slate-400 mt-2">内容管理平台</p>
      </div>
      <div class="bg-slate-800 rounded-xl shadow-xl p-8 border border-slate-700">
        <!-- 登录/注册 切换标签 -->
        <div class="flex mb-6">
          <button @click="mode='login'"
            :class="mode==='login'?'border-blue-400 text-blue-400':'border-transparent text-slate-400'"
            class="flex-1 pb-2 border-b-2 text-sm font-semibold transition">登录</button>
          <button @click="mode='register'"
            :class="mode==='register'?'border-blue-400 text-blue-400':'border-transparent text-slate-400'"
            class="flex-1 pb-2 border-b-2 text-sm font-semibold transition">注册</button>
        </div>
        <form @submit.prevent="submit" class="space-y-4">
          <!-- 注册模式：显示姓名和邮箱 -->
          <div v-if="mode==='register'">
            <label class="block text-xs text-slate-400 mb-1">姓名</label>
            <input v-model="form.full_name"
              class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition"
              placeholder="请输入姓名">
          </div>
          <div>
            <label class="block text-xs text-slate-400 mb-1">用户名</label>
            <input v-model="form.username"
              class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition"
              placeholder="请输入用户名" required>
          </div>
          <div v-if="mode==='register'">
            <label class="block text-xs text-slate-400 mb-1">邮箱</label>
            <input v-model="form.email" type="email"
              class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition"
              placeholder="请输入邮箱" required>
          </div>
          <div>
            <label class="block text-xs text-slate-400 mb-1">密码</label>
            <input v-model="form.password" type="password"
              class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition"
              placeholder="请输入密码" required>
          </div>
          <!-- 错误/成功消息 -->
          <div v-if="error" class="text-red-400 text-sm bg-red-400/10 rounded-lg px-3 py-2">{{ error }}</div>
          <div v-if="success" class="text-green-400 text-sm bg-green-400/10 rounded-lg px-3 py-2">{{ success }}</div>
          <button type="submit"
            class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg transition text-sm"
            :disabled="loading">
            {{ loading ? '请稍候...' : (mode==='login' ? '登录' : '注册') }}
          </button>
        </form>
      </div>
    </div>`,

  // 组件状态
  data() {
    return {
      mode: 'login',  // 'login' | 'register'
      form: { username: '', password: '', email: '', full_name: '' },
      error: '',
      success: '',
      loading: false,
    };
  },

  methods: {
    async submit() {
      this.error = ''; this.success = ''; this.loading = true;
      try {
        if (this.mode === 'register') {
          // 注册流程：调用 /register，成功后切换到登录模式
          await API.post('/api/v1/register', this.form);
          this.success = '注册成功！请登录。';
          this.mode = 'login';
        } else {
          // 登录流程：使用 OAuth2 表单格式提交用户名密码
          const fd = new URLSearchParams();
          fd.append('username', this.form.username);
          fd.append('password', this.form.password);
          const r = await fetch('/api/v1/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: fd
          });
          const j = await r.json();
          if (!r.ok) throw new Error(j.detail || '登录失败');
          // 保存 Token 到 localStorage，通知父组件登录成功
          localStorage.setItem('token', j.access_token);
          this.$emit('login');
        }
      } catch (e) {
        this.error = e.message;
      } finally {
        this.loading = false;
      }
    }
  }
};

// ======================== 侧边栏组件 ========================

const Sidebar = {
  template: `
    <aside class="w-56 bg-slate-800/50 border-r border-slate-700/50 flex flex-col shrink-0">
      <!-- 品牌标识 -->
      <div class="p-5">
        <div class="text-xl font-bold text-blue-400 mb-1">LightPress</div>
        <div class="text-xs text-slate-500">CMS 平台</div>
      </div>
      <!-- 导航菜单 -->
      <nav class="flex-1 px-3 space-y-1">
        <a v-for="item in navItems" :key="item.route"
          @click="$emit('navigate', item.route)"
          :class="currentRoute===item.route
            ? 'bg-blue-600/20 text-blue-400 border-blue-500/50'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 border-transparent'"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm border-l-2 cursor-pointer transition-all">
          <span v-html="item.icon"></span>{{ item.label }}
        </a>
      </nav>
      <!-- 用户信息和退出按钮 -->
      <div class="p-3 mx-3 mb-3 bg-slate-800 rounded-lg border border-slate-700/50">
        <div class="text-xs text-slate-300 font-medium truncate">
          {{ user.full_name || user.username }}
        </div>
        <div class="text-xs text-slate-500 mt-0.5">
          {{ user.roles?.join(', ') || '普通用户' }}
        </div>
        <button @click="$emit('logout')"
          class="mt-2 text-xs text-slate-500 hover:text-red-400 transition">退出登录 →</button>
      </div>
    </aside>`,

  props: ['currentRoute', 'user'],
  emits: ['navigate', 'logout'],

  data() {
    return {
      navItems: [
        { route: 'dashboard',  label: '仪表盘',   icon: '&#9776;' },
        { route: 'articles',   label: '文章管理', icon: '&#9998;' },
        { route: 'media',      label: '媒体库',   icon: '&#128247;' },
        { route: 'categories', label: '分类管理', icon: '&#128450;' },
        { route: 'tags',       label: '标签管理', icon: '&#127991;' },
        { route: 'users',      label: '用户管理', icon: '&#128101;' },
      ]
    };
  }
};

// ======================== 仪表盘组件 ========================

const Dashboard = {
  template: `
    <div>
      <h2 class="text-2xl font-bold mb-6">仪表盘</h2>
      <!-- 统计卡片：4 个核心指标 -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700/50">
          <div class="text-3xl font-bold">{{ stats.total_articles }}</div>
          <div class="text-xs text-slate-400 mt-1">文章总数</div>
        </div>
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700/50">
          <div class="text-3xl font-bold text-green-400">{{ stats.published_articles }}</div>
          <div class="text-xs text-slate-400 mt-1">已发布</div>
        </div>
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700/50">
          <div class="text-3xl font-bold text-amber-400">{{ stats.pending_articles }}</div>
          <div class="text-xs text-slate-400 mt-1">待审核</div>
        </div>
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700/50">
          <div class="text-3xl font-bold">{{ stats.total_users }}</div>
          <div class="text-xs text-slate-400 mt-1">用户数</div>
        </div>
      </div>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- 最近文章列表 -->
        <div class="lg:col-span-2 bg-slate-800 rounded-xl p-5 border border-slate-700/50">
          <h3 class="font-semibold mb-3 text-sm text-slate-300">最近文章</h3>
          <div v-if="recent.length===0" class="text-sm text-slate-500">暂无文章</div>
          <div v-for="a in recent" :key="a.id"
            class="flex items-center justify-between py-2 border-b border-slate-700/30 last:border-0 text-sm">
            <span class="text-slate-200 truncate flex-1 cursor-pointer hover:text-blue-400 transition"
              @click="$emit('navigate','articles/edit?id='+a.id)">{{ a.title }}</span>
            <span :class="statusClass(a.status)"
              class="text-xs ml-3 font-medium px-2 py-0.5 rounded-full">{{ a.status }}</span>
          </div>
        </div>
        <!-- 快捷操作 -->
        <div class="bg-slate-800 rounded-xl p-5 border border-slate-700/50">
          <h3 class="font-semibold mb-3 text-sm text-slate-300">快捷操作</h3>
          <div class="space-y-2">
            <button @click="$emit('navigate','articles/new')"
              class="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 rounded-lg transition">
              + 写文章
            </button>
            <button @click="$emit('navigate','media')"
              class="w-full bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium py-2 rounded-lg transition">
              上传文件
            </button>
          </div>
        </div>
      </div>
    </div>`,

  props: ['user', 'stats', 'recent'],

  methods: {
    // 状态样式映射（不同状态显示不同颜色）
    statusClass(s) {
      return {
        published: 'bg-green-400/20 text-green-400',
        pending: 'bg-amber-400/20 text-amber-400',
        draft: 'bg-slate-400/20 text-slate-400',
        archived: 'bg-red-400/20 text-red-400'
      }[s] || '';
    }
  }
};

// ======================== 文章列表组件 ========================

const ArticleList = {
  template: `
    <div>
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold">文章管理</h2>
        <button @click="$emit('navigate','articles/new')"
          class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
          + 写文章
        </button>
      </div>
      <!-- 筛选栏：状态 + 分类 + 关键词搜索 -->
      <div class="flex flex-wrap gap-3 mb-4">
        <select v-model="filters.status" @change="load"
          class="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="pending">待审核</option>
          <option value="published">已发布</option>
          <option value="archived">已归档</option>
        </select>
        <select v-model="filters.category_id" @change="load"
          class="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500">
          <option :value="null">全部分类</option>
          <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <input v-model="filters.keyword" @keyup.enter="load" placeholder="搜索文章..."
          class="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 flex-1 min-w-[200px] focus:outline-none focus:border-blue-500">
        <button @click="load"
          class="bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm px-4 py-2 rounded-lg transition">搜索</button>
      </div>
      <!-- 文章表格 -->
      <div class="bg-slate-800 rounded-xl border border-slate-700/50 overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-slate-700/50 text-slate-400 text-xs uppercase">
              <th class="text-left p-3">标题</th>
              <th class="text-left p-3 hidden md:table-cell">分类</th>
              <th class="text-left p-3">状态</th>
              <th class="text-left p-3">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in articles" :key="a.id"
              class="border-b border-slate-700/30 hover:bg-slate-700/20 transition">
              <td class="p-3">
                <div class="font-medium text-slate-200 cursor-pointer hover:text-blue-400 transition"
                  @click="$emit('navigate', 'articles/edit?id='+a.id)">{{ a.title }}</div>
                <div class="text-xs text-slate-500 mt-0.5">{{ a.author_name }}</div>
              </td>
              <td class="p-3 hidden md:table-cell text-slate-400">{{ a.category_name || '-' }}</td>
              <td class="p-3">
                <span :class="statusClass(a.status)"
                  class="text-xs px-2 py-0.5 rounded-full font-medium">{{ a.status }}</span>
              </td>
              <!-- 操作按钮根据文章状态和用户角色动态显示 -->
              <td class="p-3">
                <div class="flex gap-2 flex-wrap">
                  <button @click="$emit('navigate', 'articles/edit?id='+a.id)"
                    class="text-xs text-blue-400 hover:text-blue-300">编辑</button>
                  <button v-if="a.status==='draft'" @click="submitArticle(a.id)"
                    class="text-xs text-amber-400 hover:text-amber-300">提交审核</button>
                  <button v-if="a.status==='pending' && isEditor" @click="approveArticle(a.id)"
                    class="text-xs text-green-400 hover:text-green-300">通过</button>
                  <button v-if="a.status==='pending' && isEditor" @click="rejectArticle(a.id)"
                    class="text-xs text-red-400 hover:text-red-300">驳回</button>
                  <button v-if="a.status!=='archived' && isEditor" @click="archiveArticle(a.id)"
                    class="text-xs text-slate-400 hover:text-slate-300">归档</button>
                  <button @click="deleteArticle(a.id)"
                    class="text-xs text-red-400 hover:text-red-300">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="articles.length===0" class="p-8 text-center text-slate-500 text-sm">暂无文章</div>
      </div>
      <!-- 分页 -->
      <div class="flex items-center justify-between mt-4 text-sm text-slate-400">
        <span>共 {{ total }} 条</span>
        <div class="flex gap-2">
          <button @click="page--; load()" :disabled="page<=1"
            class="px-3 py-1 bg-slate-800 rounded disabled:opacity-50 hover:bg-slate-700 transition">上一页</button>
          <span class="px-3 py-1">{{ page }}</span>
          <button @click="page++; load()" :disabled="page*size>=total"
            class="px-3 py-1 bg-slate-800 rounded disabled:opacity-50 hover:bg-slate-700 transition">下一页</button>
        </div>
      </div>
    </div>`,

  props: ['user'],

  data() {
    return {
      articles: [],
      categories: [],
      filters: { status: '', category_id: null, keyword: '' },
      page: 1,
      size: 20,
      total: 0,
    };
  },

  computed: {
    // 判断当前用户是否是编辑或管理员（用于显示审核按钮）
    isEditor() {
      return (this.user.roles || []).some(r => r === 'editor' || r === 'admin')
        || this.user.is_superuser;
    }
  },

  async mounted() {
    await this.loadCategories();
    await this.load();
  },

  methods: {
    statusClass(s) {
      return {
        published: 'bg-green-400/20 text-green-400',
        pending: 'bg-amber-400/20 text-amber-400',
        draft: 'bg-slate-400/20 text-slate-400',
        archived: 'bg-red-400/20 text-red-400'
      }[s] || '';
    },

    async loadCategories() {
      this.categories = await API.get('/api/v1/categories');
    },

    async load() {
      // 构建查询参数
      const p = new URLSearchParams({ page: this.page, size: this.size });
      if (this.filters.status) p.set('status', this.filters.status);
      if (this.filters.category_id) p.set('category_id', this.filters.category_id);
      if (this.filters.keyword) p.set('keyword', this.filters.keyword);
      const d = await API.get('/api/v1/articles?' + p.toString());
      this.articles = d.items;
      this.total = d.total;
      this.page = d.page;
    },

    // ===== 文章工作流操作 =====
    async submitArticle(id) {
      try { await API.post('/api/v1/articles/' + id + '/submit'); await this.load(); }
      catch (e) { alert(e.message); }
    },
    async approveArticle(id) {
      try { await API.post('/api/v1/articles/' + id + '/approve'); await this.load(); }
      catch (e) { alert(e.message); }
    },
    async rejectArticle(id) {
      const c = prompt('驳回理由（可选）：');
      try { await API.post('/api/v1/articles/' + id + '/reject', { comment: c || '' }); await this.load(); }
      catch (e) { alert(e.message); }
    },
    async archiveArticle(id) {
      try { await API.post('/api/v1/articles/' + id + '/archive'); await this.load(); }
      catch (e) { alert(e.message); }
    },
    async deleteArticle(id) {
      if (confirm('确定删除这篇文章？')) {
        try { await API.delete('/api/v1/articles/' + id); await this.load(); }
        catch (e) { alert(e.message); }
      }
    },
  }
};

// ======================== 文章编辑器组件 ========================

const ArticleEditor = {
  template: `
    <div>
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold">{{ isEdit ? '编辑文章' : '新建文章' }}</h2>
        <button @click="$emit('done')" class="text-sm text-slate-400 hover:text-slate-200">← 返回</button>
      </div>
      <div class="bg-slate-800 rounded-xl border border-slate-700/50 p-6 space-y-4">
        <!-- 标题 -->
        <div>
          <label class="block text-xs text-slate-400 mb-1">标题</label>
          <input v-model="form.title"
            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
            placeholder="请输入文章标题">
        </div>
        <!-- 摘要 -->
        <div>
          <label class="block text-xs text-slate-400 mb-1">摘要</label>
          <input v-model="form.excerpt"
            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
            placeholder="简要描述">
        </div>
        <!-- 分类 + 标签（并排） -->
        <div class="flex gap-4">
          <div class="flex-1">
            <label class="block text-xs text-slate-400 mb-1">分类</label>
            <select v-model="form.category_id"
              class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500">
              <option :value="null">无分类</option>
              <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="flex-1">
            <label class="block text-xs text-slate-400 mb-1">标签（逗号分隔）</label>
            <input v-model="tagInput" @change="updateTags"
              class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
              placeholder="python, 测试">
          </div>
        </div>
        <!-- 正文 -->
        <div>
          <label class="block text-xs text-slate-400 mb-1">正文</label>
          <textarea v-model="form.content" rows="15"
            class="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 font-mono"
            placeholder="请输入文章内容..."></textarea>
        </div>
        <!-- 操作按钮 -->
        <div class="flex gap-3 pt-2">
          <button @click="saveDraft"
            class="bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium px-6 py-2.5 rounded-lg transition">
            保存草稿
          </button>
          <button v-if="isEdit" @click="submitArticle"
            class="bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition">
            提交审核
          </button>
        </div>
      </div>
    </div>`,

  props: ['articleId', 'user'],
  emits: ['done'],

  data() {
    return {
      form: { title: '', content: '', excerpt: '', category_id: null, tag_ids: [] },
      tagInput: '',          // 标签输入框的原始文本（逗号分隔的标签名）
      categories: [],
      tags: [],              // 所有已存在的标签列表（用于匹配）
      existingArticle: null, // 编辑模式下加载的现有文章
    };
  },

  computed: {
    isEdit() { return !!this.existingArticle; }
  },

  async mounted() {
    // 加载分类和已有标签列表
    this.categories = await API.get('/api/v1/categories');
    const allTags = await API.get('/api/v1/tags');
    this.tags = allTags;

    // 编辑模式：加载现有文章内容填入表单
    if (this.articleId) {
      this.existingArticle = await API.get('/api/v1/articles/' + this.articleId);
      this.form = {
        title: this.existingArticle.title,
        content: this.existingArticle.content,
        excerpt: this.existingArticle.excerpt,
        category_id: this.existingArticle.category_id,
        tag_ids: this.existingArticle.tags.map(t => t.id),
      };
      this.tagInput = this.existingArticle.tags.map(t => t.name).join(', ');
    }
  },

  methods: {
    // 将逗号分隔的标签名转换为标签 ID 列表
    updateTags() {
      const names = this.tagInput.split(',').map(s => s.trim()).filter(Boolean);
      const ids = [];
      names.forEach(n => {
        const found = this.tags.find(t => t.name.toLowerCase() === n.toLowerCase());
        if (found) ids.push(found.id);
      });
      this.form.tag_ids = ids;
    },

    // 保存草稿：新建时 POST，编辑时 PATCH
    async saveDraft() {
      try {
        if (this.isEdit) {
          await API.patch('/api/v1/articles/' + this.articleId, this.form);
        } else {
          await API.post('/api/v1/articles', this.form);
        }
        this.$emit('done');  // 通知父组件返回文章列表
      } catch (e) { alert(e.message); }
    },

    // 提交审核：先保存再提交刚创建/编辑的文章
    async submitArticle() {
      await this.saveDraft();
      try {
        const list = await API.get('/api/v1/articles/my?page=1&size=1');
        if (list.items.length > 0) {
          await API.post('/api/v1/articles/' + list.items[0].id + '/submit');
        }
        this.$emit('done');
      } catch (e) { alert(e.message); }
    }
  }
};

// ======================== 媒体库组件 ========================

const MediaLibrary = {
  template: `
    <div>
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold">媒体库</h2>
        <!-- 隐藏的原生文件选择器，用美观的 label 触发 -->
        <label class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg cursor-pointer transition">
          + 上传
          <input type="file" @change="uploadFile" class="hidden" multiple>
        </label>
      </div>
      <div v-if="uploading" class="text-sm text-blue-400 mb-3">上传中...</div>
      <div v-if="items.length===0" class="text-center text-slate-500 py-12">暂无文件</div>
      <!-- 文件网格：图片直接预览，非图片显示文件图标 -->
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div v-for="m in items" :key="m.id"
          class="bg-slate-800 rounded-xl border border-slate-700/50 overflow-hidden group">
          <div class="aspect-square bg-slate-900 flex items-center justify-center overflow-hidden">
            <img v-if="m.mime_type && m.mime_type.startsWith('image/')"
              :src="'/api/v1/media/'+m.id" class="w-full h-full object-cover" :alt="m.original_name">
            <span v-else class="text-3xl text-slate-600">&#128196;</span>
          </div>
          <div class="p-2 text-xs">
            <div class="text-slate-300 truncate" :title="m.original_name">{{ m.original_name }}</div>
            <div class="text-slate-500 flex justify-between mt-1">
              <span>{{ formatSize(m.file_size) }}</span>
              <!-- 删除按钮：hover 时显示 -->
              <button @click="deleteMedia(m.id)"
                class="text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition">删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>`,

  props: ['user'],

  data() {
    return { items: [], total: 0, page: 1, uploading: false };
  },

  async mounted() { await this.load(); },

  methods: {
    // 格式化文件大小显示
    formatSize(b) {
      return b > 1048576 ? (b / 1048576).toFixed(1) + 'MB'
        : b > 1024 ? (b / 1024).toFixed(1) + 'KB'
        : b + 'B';
    },

    async load() {
      const d = await API.get('/api/v1/media?page=' + this.page + '&size=50');
      this.items = d.items;
      this.total = d.total;
    },

    // 上传文件：支持多选，逐个上传
    async uploadFile(e) {
      const files = e.target.files;
      this.uploading = true;
      for (const f of files) {
        try {
          const fd = new FormData();
          fd.append('file', f);
          await API.upload('/api/v1/media/upload', fd);
        } catch (e) { alert(e.message); }
      }
      this.uploading = false;
      e.target.value = '';  // 清空选择以便重复选择同一文件
      await this.load();
    },

    async deleteMedia(id) {
      if (confirm('确定删除？')) {
        try { await API.delete('/api/v1/media/' + id); await this.load(); }
        catch (e) { alert(e.message); }
      }
    },
  }
};

// ======================== 分类管理组件 ========================

const CategoryManager = {
  template: `
    <div>
      <h2 class="text-2xl font-bold mb-6">分类管理</h2>
      <!-- 新建分类表单 -->
      <div class="flex gap-3 mb-6">
        <input v-model="form.name"
          class="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
          placeholder="分类名称">
        <input v-model="form.description"
          class="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
          placeholder="分类描述">
        <button @click="create"
          class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition">
          添加
        </button>
      </div>
      <!-- 分类列表 -->
      <div class="space-y-2">
        <div v-for="c in categories" :key="c.id"
          class="flex items-center justify-between bg-slate-800 rounded-lg border border-slate-700/50 px-4 py-3">
          <div>
            <span class="text-sm text-slate-200">{{ c.name }}</span>
            <span class="text-xs text-slate-500 ml-3">{{ c.description }}</span>
          </div>
          <button v-if="user.is_superuser" @click="remove(c.id)"
            class="text-xs text-red-400 hover:text-red-300">删除</button>
        </div>
        <div v-if="categories.length===0" class="text-center text-slate-500 text-sm py-8">暂无分类</div>
      </div>
    </div>`,

  props: ['user'],

  data() {
    return { categories: [], form: { name: '', description: '' } };
  },

  async mounted() { await this.load(); },

  methods: {
    async load() { this.categories = await API.get('/api/v1/categories'); },

    async create() {
      try {
        await API.post('/api/v1/categories', this.form);
        this.form = { name: '', description: '' };
        await this.load();
      } catch (e) { alert(e.message); }
    },

    async remove(id) {
      try { await API.delete('/api/v1/categories/' + id); await this.load(); }
      catch (e) { alert(e.message); }
    },
  }
};

// ======================== 标签管理组件 ========================

const TagManager = {
  template: `
    <div>
      <h2 class="text-2xl font-bold mb-6">标签管理</h2>
      <div class="flex gap-3 mb-6">
        <input v-model="name" @keyup.enter="create"
          class="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
          placeholder="标签名称">
        <button @click="create"
          class="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-6 py-2.5 rounded-lg transition">
          添加
        </button>
      </div>
      <!-- 标签云：每个标签显示名称和关联文章数 -->
      <div class="flex flex-wrap gap-2">
        <div v-for="t in tags" :key="t.id"
          class="flex items-center gap-2 bg-slate-800 border border-slate-700/50 rounded-lg px-3 py-2">
          <span class="text-sm text-slate-200">{{ t.name }}</span>
          <span class="text-xs text-slate-500">{{ t.article_count }} 篇文章</span>
          <button v-if="user.is_superuser" @click="remove(t.id)"
            class="text-xs text-red-400 hover:text-red-300 ml-1">&times;</button>
        </div>
        <div v-if="tags.length===0" class="text-center text-slate-500 text-sm w-full py-8">暂无标签</div>
      </div>
    </div>`,

  props: ['user'],

  data() {
    return { tags: [], name: '' };
  },

  async mounted() { await this.load(); },

  methods: {
    async load() { this.tags = await API.get('/api/v1/tags'); },

    async create() {
      if (!this.name.trim()) return;
      try {
        await API.post('/api/v1/tags', { name: this.name.trim() });
        this.name = '';
        await this.load();
      } catch (e) { alert(e.message); }
    },

    async remove(id) {
      try { await API.delete('/api/v1/tags/' + id); await this.load(); }
      catch (e) { alert(e.message); }
    },
  }
};

// ======================== 用户管理组件（管理员专用） ========================

const UserManager = {
  template: `
    <div>
      <h2 class="text-2xl font-bold mb-6">用户管理</h2>
      <div v-if="!isAdmin" class="text-slate-500 text-sm">需要管理员权限</div>
      <template v-else>
        <div class="bg-slate-800 rounded-xl border border-slate-700/50 overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-slate-700/50 text-slate-400 text-xs uppercase">
                <th class="text-left p-3">用户</th>
                <th class="text-left p-3 hidden md:table-cell">邮箱</th>
                <th class="text-left p-3">角色</th>
                <th class="text-left p-3">状态</th>
                <th class="text-left p-3">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id"
                class="border-b border-slate-700/30 hover:bg-slate-700/20 transition">
                <td class="p-3">
                  <div class="font-medium text-slate-200">{{ u.full_name || u.username }}</div>
                  <div class="text-xs text-slate-500">{{ u.username }}</div>
                </td>
                <td class="p-3 hidden md:table-cell text-slate-400">{{ u.email }}</td>
                <td class="p-3 text-slate-400 text-xs">{{ u.roles?.join(', ') || '-' }}</td>
                <td class="p-3">
                  <span :class="u.is_active?'text-green-400':'text-red-400'" class="text-xs">
                    {{ u.is_active ? '正常' : '已禁用' }}
                  </span>
                </td>
                <td class="p-3">
                  <!-- 不能停用自己 -->
                  <button v-if="u.is_active && u.id!==user.id" @click="deactivate(u.id)"
                    class="text-xs text-red-400 hover:text-red-300">停用</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>`,

  props: ['user'],

  computed: {
    isAdmin() {
      return this.user.is_superuser || (this.user.roles || []).includes('admin');
    }
  },

  data() { return { users: [] }; },

  async mounted() {
    if (this.isAdmin) await this.load();
  },

  methods: {
    async load() {
      try { this.users = await API.get('/api/v1/users?size=100'); }
      catch (e) { /* 静默处理错误 */ }
    },

    // 停用用户（软删除：将 is_active 设为 false）
    async deactivate(id) {
      if (confirm('确定停用此用户？')) {
        try { await API.delete('/api/v1/users/' + id); await this.load(); }
        catch (e) { alert(e.message); }
      }
    },
  }
};

// ======================== 根组件：应用入口 ========================

createApp({
  // 注册所有子组件
  components: {
    LoginForm, Sidebar, Dashboard, ArticleList, ArticleEditor,
    MediaLibrary, CategoryManager, TagManager, UserManager
  },

  data() {
    return {
      loading: true,        // 应用初始化加载状态
      currentRoute: 'login', // 当前路由（hash 路径）
      routeParam: null,     // 路由参数（如文章 ID）
      user: null,           // 当前登录用户信息
      stats: {              // 仪表盘统计数据
        total_articles: 0, published_articles: 0, pending_articles: 0,
        draft_articles: 0, total_users: 0, total_categories: 0,
        total_tags: 0, total_media: 0
      },
      recent: [],           // 最近文章列表
    };
  },

  async mounted() {
    // 应用启动：检查是否有已保存的 Token，自动恢复登录状态
    if (API.token()) {
      try {
        this.user = await API.get('/api/v1/me');
        this.currentRoute = 'dashboard';
        await this.loadDashboard();
      } catch (e) {
        // Token 无效/过期 → 清除并跳转登录页
        localStorage.removeItem('token');
        this.currentRoute = 'login';
      }
    }
    this.loading = false;

    // 监听 hash 变化实现路由切换
    window.addEventListener('hashchange', this.parseRoute);
    this.parseRoute();  // 首次加载解析当前 hash
  },

  methods: {
    // 解析 URL hash 为路由和参数
    // 例如 #/articles/edit?id=5 → route='articles/edit', param='5'
    parseRoute() {
      const hash = window.location.hash.slice(1) || 'login';
      const [route, qs] = hash.split('?');
      this.currentRoute = route;
      this.routeParam = null;
      if (qs) {
        const params = new URLSearchParams(qs);
        this.routeParam = params.get('id') || null;
      }
    },

    // 编程式导航：修改 hash 触发路由切换
    navigate(route) { window.location.hash = route; },

    // 登录成功回调：获取用户信息并跳转仪表盘
    async onLogin() {
      this.user = await API.get('/api/v1/me');
      await this.loadDashboard();
      this.navigate('dashboard');
    },

    // 加载仪表盘数据
    async loadDashboard() {
      try {
        this.stats = await API.get('/api/v1/dashboard/stats');
        this.recent = await API.get('/api/v1/dashboard/recent');
      } catch (e) { /* 静默处理 */ }
    },

    // 退出登录：清除 Token 和用户信息
    logout() {
      localStorage.removeItem('token');
      this.user = null;
      this.navigate('login');
    },
  }
}).mount('#app');
