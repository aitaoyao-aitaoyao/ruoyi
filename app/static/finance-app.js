const BASE = '/api/v1/finance';

function fmt(n) { return n != null ? Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'; }
function fmtInt(n) { return n != null ? Number(n).toLocaleString('zh-CN') : '0'; }
function fmtDate(d) { return d ? d.split('T')[0] : ''; }
function daysLeft(d) { const diff = new Date(d) - new Date(); return Math.ceil(diff / 86400000); }
function todayStr() { return new Date().toISOString().slice(0, 10); }
function nowStr() { return new Date().toISOString().slice(0, 16); }
// 动态 Y轴单位：大额用万，中额用千，小额直接显示
function axisUnit(v) {
    const abs = Math.abs(v);
    if (abs >= 10000) return '¥' + (v / 10000).toFixed(1) + '万';
    if (abs >= 1000) return '¥' + (v / 1000).toFixed(1) + '千';
    return '¥' + v;
}
function axisUnitWan(v) {
    if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + '万';
    return '¥' + v;
}

function getToken() { return localStorage.getItem('finance_token'); }
function setToken(t) { localStorage.setItem('finance_token', t); }
function clearToken() { localStorage.removeItem('finance_token'); localStorage.removeItem('finance_user'); }

async function api(url, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    const token = getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    const res = await fetch(BASE + url, { headers, ...opts });
    if (res.status === 401) {
        clearToken();
        window.location.hash = '#/finance/login';
        throw new Error('登录已过期，请重新登录');
    }
    if (res.status === 204) return null;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
}

// ---- Shared toast state ----
const sharedToast = Vue.reactive({ show: false, message: '', type: 'success' });

const ToastMixin = {
    methods: {
        showToast(msg, type = 'success') {
            sharedToast.show = true;
            sharedToast.message = msg;
            sharedToast.type = type;
            setTimeout(() => { sharedToast.show = false; }, 3000);
        },
    },
};

// ---- Batch delete helper ----
const BatchDeleteMixin = {
    data() {
        return { selectedIds: [] };
    },
    methods: {
        toggleSelect(id) {
            const idx = this.selectedIds.indexOf(id);
            if (idx >= 0) this.selectedIds.splice(idx, 1);
            else this.selectedIds.push(id);
        },
        toggleSelectAll() {
            if (this.selectedIds.length === this.items.length) {
                this.selectedIds = [];
            } else {
                this.selectedIds = this.items.map(it => it.id);
            }
        },
        async batchDelete(delFn) {
            if (this.selectedIds.length === 0) return this.showToast('请先选择要删除的项', 'error');
            if (!confirm('确定删除选中的 ' + this.selectedIds.length + ' 条记录吗？')) return;
            try {
                for (const id of this.selectedIds) {
                    await delFn(id);
                }
                this.showToast('已删除 ' + this.selectedIds.length + ' 条');
                this.selectedIds = [];
                await this.load();
            } catch(e) { this.showToast(e.message, 'error'); }
        },
    },
};

// ---- Login Page ----
const LoginPage = {
    template: `
<div class="login-page">
    <canvas ref="bgCanvas" class="login-bg"></canvas>
    <div class="login-card">
        <div class="login-brand">
            <div class="login-logo">财智管家</div>
            <div class="login-subtitle">Personal Finance Intelligence</div>
        </div>
        <form @submit.prevent="login" class="login-form">
            <div class="login-input-group">
                <input v-model="username" type="text" placeholder="用户名" autocomplete="username" required>
            </div>
            <div class="login-input-group">
                <input v-model="password" type="password" placeholder="密码" autocomplete="current-password" required>
            </div>
            <div v-if="error" class="login-error">{{ error }}</div>
            <button type="submit" class="login-btn" :disabled="loading">
                {{ loading ? '登录中...' : '登 录' }}
            </button>
        </form>
    </div>
</div>`,
    data() {
        return { username: '', password: '', error: '', loading: false, _animId: null };
    },
    mounted() {
        if (getToken()) { router.push('/finance/dashboard'); return; }
        this.$nextTick(() => this.initBg());
    },
    beforeUnmount() {
        if (this._animId) cancelAnimationFrame(this._animId);
    },
    methods: {
        async login() {
            this.error = '';
            if (!this.username || !this.password) { this.error = '请输入用户名和密码'; return; }
            this.loading = true;
            try {
                const body = new URLSearchParams({ username: this.username, password: this.password });
                const res = await fetch('/api/v1/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || '登录失败');
                setToken(data.access_token);
                localStorage.setItem('finance_user', this.username);
                router.push('/finance/dashboard');
            } catch (e) {
                this.error = e.message;
            } finally {
                this.loading = false;
            }
        },
        initBg() {
            const canvas = this.$refs.bgCanvas;
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const particles = [];
            for (let i = 0; i < 80; i++) {
                particles.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height,
                    r: Math.random() * 2 + 0.5,
                    vx: (Math.random() - 0.5) * 0.5,
                    vy: (Math.random() - 0.5) * 0.5,
                    o: Math.random() * 0.5 + 0.1,
                });
            }
            const self = this;
            const animate = () => {
                self._animId = requestAnimationFrame(animate);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                particles.forEach((p, i) => {
                    p.x += p.vx; p.y += p.vy;
                    if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                    if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                    ctx.fillStyle = 'rgba(79,172,254,' + p.o + ')';
                    ctx.fill();
                    for (let j = i + 1; j < particles.length; j++) {
                        const dx = p.x - particles[j].x;
                        const dy = p.y - particles[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < 100) {
                            ctx.beginPath();
                            ctx.moveTo(p.x, p.y);
                            ctx.lineTo(particles[j].x, particles[j].y);
                            ctx.strokeStyle = 'rgba(79,172,254,' + (0.1 * (1 - dist / 100)) + ')';
                            ctx.stroke();
                        }
                    }
                });
            };
            this._animId = requestAnimationFrame(animate);
            window.addEventListener('resize', () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; });
        }
    }
};

// ---- ECharts cleanup mixin ----
const ChartMixin = {
    data() {
        return { _charts: [] };
    },
    methods: {
        _initChart(el) {
            if (!el) return null;
            const chart = echarts.init(el);
            const onResize = () => chart.resize();
            window.addEventListener('resize', onResize);
            this._charts.push({ chart, onResize });
            return chart;
        },
        _disposeCharts() {
            this._charts.forEach(({ chart, onResize }) => {
                window.removeEventListener('resize', onResize);
                chart.dispose();
            });
            this._charts = [];
        },
    },
    beforeUnmount() {
        this._disposeCharts();
    },
};

// ---- Dashboard ----
const DashboardPage = {
    mixins: [ToastMixin, ChartMixin],
    template: `
<div>
    <div class="page-header"><h2>仪表盘 <span v-if="v2.risk" class="v2-risk-badge" style="position:static;display:inline-block;margin-left:8px;vertical-align:middle;font-size:12px;padding:3px 12px" :style="{ background: v2.risk.overall.color + '22', color: v2.risk.overall.color, border: '1px solid ' + v2.risk.overall.color + '44' }">{{ v2.risk.overall.grade }} · {{ v2.risk.overall.label }}</span></h2><p>个人财务概览</p></div>
    <div class="stat-cards">
        <div class="stat-card"><div class="label">总负债（含房贷）</div><div class="value red">{{ fmt(dash.total_debt) }}</div></div>
        <div class="stat-card"><div class="label">总负债（不含房贷）</div><div class="value red">{{ fmt(dash.total_debt_ex_mortgage) }}</div></div>
        <div class="stat-card"><div class="label">总资产</div><div class="value green">{{ fmt(dash.total_assets) }}</div></div>
        <div class="stat-card" style="cursor:pointer" @click="showInterestDetail"><div class="label">本月应付利息</div><div class="value yellow">{{ fmt(dash.monthly_interest) }}</div></div>
        <div class="stat-card"><div class="label">本月 POS 手续费</div><div class="value blue">{{ fmt(dash.monthly_pos_fee) }}</div></div>
        <div class="stat-card"><div class="label">净资产</div><div class="value" :style="{ color: netWorth >= 0 ? 'var(--green)' : 'var(--red)' }">{{ fmt(netWorth) }}</div></div>
        <div class="stat-card"><div class="label">月预算执行率</div><div class="value" :style="{ color: budgetRate > 100 ? 'var(--red)' : 'var(--green)' }">{{ budgetRate > 0 ? budgetRate + '%' : '-' }}</div></div>
    </div>
    <div class="section-title">风险指标</div>
    <div class="stat-cards" v-if="v2.metrics && Object.keys(v2.metrics).length">
        <div class="stat-card v2-stat tooltip-card" v-for="(m, key) in v2.metrics" :key="key" :style="{ borderLeft: '3px solid ' + m.risk_color }">
            <div class="label">{{ metricLabel(key) }}</div>
            <div class="value" :style="{ color: m.risk_color, fontSize: '22px' }">{{ m.formatted }}</div>
            <div style="font-size:10px;color:#888;margin-top:4px">{{ m.description }}</div>
            <span class="v2-risk-badge" :style="{ background: m.risk_color + '22', color: m.risk_color, border: '1px solid ' + m.risk_color + '44' }">{{ m.risk_label }}</span>
            <span class="tooltip-text">{{ metricTooltip(key) }}</span>
        </div>
    </div>
    <div class="section-title">负债明细 <span style="font-size:10px;color:#666;font-weight:normal">（点击管理）</span></div>
    <div class="stat-cards">
        <div class="stat-card" style="cursor:pointer" @click="navigate('/finance/loans')">
            <div class="label">贷款负债</div><div class="value red">{{ fmt(dash.total_loan_debt) }}</div>
        </div>
        <div class="stat-card" style="cursor:pointer" @click="navigate('/finance/credit-cards')">
            <div class="label">信用卡负债</div><div class="value blue">{{ fmt(dash.total_card_debt) }}</div>
        </div>
        <div class="stat-card" style="cursor:pointer" @click="navigate('/finance/installments')">
            <div class="label">分期负债</div><div class="value yellow">{{ fmt(dash.total_installment_debt) }}</div>
        </div>
        <div class="stat-card" style="cursor:pointer" @click="navigate('/finance/mortgages')">
            <div class="label">房贷负债</div><div class="value green">{{ fmt(dash.total_mortgage_debt) }}</div>
        </div>
    </div>
    <div class="chart-row">
        <div class="chart-box"><div class="title">负债分布</div><div ref="pieChart" class="chart-inner"></div></div>
        <div class="chart-box"><div class="title">负债趋势（近12月快照）</div><div ref="trendChart" class="chart-inner"></div></div>
    </div>
    <div v-if="overdueRepayments && overdueRepayments.length" class="section-title" style="color:var(--red)">⚠ 逾期还款（{{ overdueRepayments.length }}条，请逐条确认）</div>
    <div v-for="r in overdueRepayments" :key="'od'+r.id" class="remind-item urgent" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div><span class="badge red">逾期{{ r.days_overdue }}天</span>
            <strong style="margin-left:8px">{{ r.name }}</strong> <span style="color:#888">({{ r.person_name }})</span>
            <span style="color:#888;margin-left:4px;font-size:11px">第{{ r.period_no }}期 · {{ r.due_date }}</span>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
            <div style="font-weight:bold;font-size:14px;color:var(--red)">¥{{ fmt(r.amount) }}</div>
            <button class="btn btn-secondary btn-xs" @click="markOverduePaid(r.id)">确认已还</button>
            <button class="btn btn-secondary btn-xs" @click="confirmOverdue(r.id)" style="color:var(--yellow)">确认逾期</button>
        </div>
    </div>

    <div class="section-title">最近7天还款提醒</div>
    <div v-if="reminders.length === 0 && (!overdueRepayments || !overdueRepayments.length)" class="empty-state">暂无到期提醒</div>
    <div v-for="r in reminders" :key="r.type + r.name" class="remind-item" :class="r.days_left <= 1 ? 'urgent' : r.days_left <= 3 ? 'warning' : 'normal'">
        <div><span :class="'badge ' + (r.type === 'loan' ? 'red' : r.type === 'card' ? 'blue' : 'yellow')">{{ typeLabel(r.type) }}</span>
            <strong style="margin-left:8px">{{ r.name }}</strong> <span style="color:#888">({{ r.person_name }})</span>
            <span v-if="r.card_last4" style="color:#888;margin-left:4px">尾号{{ r.card_last4 }}</span>
        </div>
        <div style="text-align:right">
            <div style="font-weight:bold;font-size:14px" :class="r.days_left <= 1 ? 'red' : ''">¥{{ fmt(r.amount) }}</div>
            <div style="font-size:11px;color:#888">到期: {{ r.due_date }} · 还剩 <span :style="{ color: r.days_left <= 1 ? 'var(--red)' : r.days_left <= 3 ? 'var(--yellow)' : 'var(--blue)' }">{{ r.days_left }} 天</span></div>
        </div>
    </div>
    <div class="section-title">收支缺口分析</div>
    <div class="chart-row">
        <div class="chart-box" style="grid-column: 1 / -1"><div class="title">月度收支缺口（近12个月）</div><div ref="gapChart" class="chart-inner"></div></div>
    </div>
    <div class="chart-row">
        <div class="chart-box" style="grid-column: 1 / -1"><div class="title">净资产趋势（近12个月）</div><div ref="netWorthChart" class="chart-inner" style="height:260px"></div></div>
    </div>

    <!-- 利息明细弹窗 -->
    <div v-if="showInterestModal" class="modal-overlay" @click.self="showInterestModal = false">
        <div class="modal" style="width:600px;max-height:70vh">
            <h3>本月应付利息明细 — {{ interestDetail.period }}</h3>
            <div style="font-size:20px;font-weight:bold;color:var(--yellow);margin-bottom:16px">
                合计: ¥{{ fmt(interestDetail.total) }}
            </div>
            <table class="data-table" v-if="interestDetail.items.length > 0">
                <thead><tr>
                    <th>类型</th><th>名称</th><th>人员</th><th>到期日</th><th>金额</th><th>备注</th>
                </tr></thead>
                <tbody><tr v-for="(item, idx) in interestDetail.items" :key="idx">
                    <td><span :class="'tag ' + interestTypeClass(item.type)">{{ item.type }}</span></td>
                    <td>{{ item.name }}</td>
                    <td>{{ item.person_name }}</td>
                    <td>{{ item.due_date }}</td>
                    <td :style="{ color: 'var(--yellow)', fontWeight: 'bold' }">¥{{ fmt(item.amount) }}</td>
                    <td style="color:#888;font-size:11px">{{ item.note }}</td>
                </tr></tbody>
            </table>
            <div v-else class="empty-state">本月暂无应付利息</div>
            <div style="margin-top:16px;text-align:right">
                <button class="btn btn-secondary" @click="showInterestModal = false">关闭</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return {
            dash: {}, reminders: [], snapshots: [], cashHistory: [], overdueRepayments: [],
            showInterestModal: false,
            interestDetail: { total: 0, period: '', items: [] },
            monthlyBudget: 0,
            v2: { period: '', inputs: {}, metrics: {} },
        };
    },
    async mounted() {
        try { this.dash = await api('/dashboard'); } catch(e) { this.showToast(e.message, 'error'); }
        try { this.reminders = await api('/repay-reminders'); } catch(e) { this.showToast(e.message, 'error'); }
        try { const od = await api('/repay-overdue'); this.overdueRepayments = od.items || []; } catch(e) {}
        try { this.snapshots = await api('/reports/snapshots?months=12'); } catch(e) {}
        try { this.v2 = await api('/v2/dashboard'); } catch(e) {}
        try { const riskData = await api('/v2/risk-assessment'); this.v2.risk = riskData; } catch(e) {}
        try { this.cashHistory = await api('/settings/cash/history?limit=12'); } catch(e) {}
        try { const b = await api('/settings/app/budget'); this.monthlyBudget = parseFloat(b.value) || 0; } catch(e) {}
        this.$nextTick(() => { this.renderPie(); this.renderTrend(); this.renderGap(); this.renderNetWorth(); });
    },
    computed: {
        netWorth() {
            const cash = (this.v2 && this.v2.inputs && this.v2.inputs.cash_on_hand) || 0;
            const debt = (this.dash && this.dash.total_debt) || 0;
            return cash - debt;
        },
        budgetRate() {
            if (!this.monthlyBudget) return 0;
            const expense = (this.v2 && this.v2.inputs && this.v2.inputs.monthly_expense) || 0;
            return Math.round(expense / this.monthlyBudget * 100);
        }
    },
    methods: {
        fmt, fmtDate, daysLeft,
        navigate(path) { router.push(path); },
        typeLabel(t) { const m = { loan: '贷款', card: '信用卡', installment: '分期' }; return m[t] || t; },
        metricLabel(k) { const m = { debt_burn_rate: '债务燃烧率', survival_line: '生存线', debt_freedom_months: '债务自由预期', cash_flow_rupture: '现金流破裂预警', interest_consumption_rate: '利息消耗率' }; return m[k] || k; },
        metricTooltip(k) { const m = { debt_burn_rate: '月利息 + 月手续费 − 月减少本金。正值=债务恶化，负值=债务下降', survival_line: '月收入 − 月支出 − 月利息。正值=止血有结余，负值=持续失血', debt_freedom_months: '总负债 ÷ 生存线。按当前结余速度预计还清全部债务的月数', cash_flow_rupture: '手头现金 ÷ |月缺口|。手头现金能支撑多少个月不被耗尽', interest_consumption_rate: '月利息 ÷ 月收入 × 100%。利息占收入比例，越高越危险' }; return m[k] || ''; },
        async markOverduePaid(rpId) {
            try { await api('/loans/repayments/' + rpId + '/pay', { method: 'PATCH' }); this.showToast('已标记还款'); this.overdueRepayments = await api('/repay-overdue'); this.reminders = await api('/repay-reminders'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async confirmOverdue(rpId) {
            if (!confirm('确认此还款确实逾期？确认后将从逾期列表中移除。')) return;
            this.overdueRepayments = this.overdueRepayments.filter(r => r.id !== rpId);
            this.showToast('已确认逾期，请尽快处理');
        },
        async showInterestDetail() {
            try {
                this.interestDetail = await api('/monthly-interest-detail');
                this.showInterestModal = true;
            } catch(e) { this.showToast(e.message, 'error'); }
        },
        interestTypeClass(type) {
            if (type.includes('贷款')) return 'red';
            if (type.includes('信用卡')) return 'blue';
            if (type.includes('分期')) return 'yellow';
            if (type.includes('房贷')) return 'green';
            return '';
        },
        renderPie() {
            const el = this.$refs.pieChart; if (!el) return;
            const chart = this._initChart(el);
            const labels = ['贷款', '信用卡', '分期', '房贷'];
            const values = [this.dash.total_loan_debt || 0, this.dash.total_card_debt || 0, this.dash.total_installment_debt || 0, this.dash.total_mortgage_debt || 0];
            const colors = ['#e94560', '#4facfe', '#f9ca24', '#00d2a0'];
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: ¥{c}' },
                series: [{
                    type: 'pie', radius: ['45%', '75%'], center: ['50%', '55%'],
                    data: labels.map((n,i) => ({ value: values[i], name: n, itemStyle: { color: colors[i] } })),
                    label: { color: '#888', fontSize: 11 },
                    emphasis: { label: { fontSize: 16, fontWeight: 'bold' } }
                }]
            });
        },
        renderTrend() {
            const el = this.$refs.trendChart; if (!el) return;
            const chart = this._initChart(el);
            const dates = this.snapshots.map(s => s.snapshot_date);
            const data = this.snapshots.map(s => s.total_debt);
            if (dates.length === 0) { chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } }); return; }
            chart.setOption({
                tooltip: { trigger: 'axis' },
                grid: { left: 60, right: 20, top: 20, bottom: 60 },
                xAxis: { type: 'category', data: dates, axisLabel: { color: '#888', fontSize: 10, rotate: 45, interval: 0 }, axisTick: { alignWithLabel: true } },
                yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => axisUnitWan(v) }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                series: [{ type: 'line', data, smooth: true, lineStyle: { color: '#e94560', width: 2 }, areaStyle: { color: 'rgba(233,69,96,0.1)' }, itemStyle: { color: '#e94560' } }]
            });
        },
        renderGap() {
            const el = this.$refs.gapChart; if (!el) return;
            const chart = this._initChart(el);
            const now = new Date();
            const months = [];
            for (let i = 11; i >= 0; i--) {
                const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
                months.push(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'));
            }
            Promise.all(months.map(m => api('/reports/gap-analysis?year=' + m.split('-')[0] + '&month=' + m.split('-')[1]).catch(() => ({ gap: 0, total_income: 0, total_expense: 0 }))))
                .then(results => {
                    chart.setOption({
                        tooltip: { trigger: 'axis', formatter: p => {
                            const d = results[p[0].dataIndex];
                            return p[0].name + '<br/>收入: ¥' + fmt(d.total_income) + '<br/>支出: ¥' + fmt(d.total_expense) + '<br/>缺口: ¥' + fmt(-d.gap);
                        }},
                        grid: { left: 60, right: 20, top: 20, bottom: 30 },
                        legend: { data: ['收入', '支出', '缺口'], textStyle: { color: '#888', fontSize: 11 }, top: 0 },
                        xAxis: { type: 'category', data: months, axisLabel: { color: '#888', fontSize: 10 } },
                        yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => axisUnit(v) }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                        series: [
                            { name: '收入', type: 'bar', data: results.map(r => r.total_income), itemStyle: { color: '#00d2a0' }, barGap: 0 },
                            { name: '支出', type: 'bar', data: results.map(r => r.total_expense), itemStyle: { color: '#e94560' } },
                            { name: '缺口', type: 'line', data: results.map(r => -r.gap), lineStyle: { color: '#f9ca24' }, itemStyle: { color: '#f9ca24' }, symbol: 'diamond' },
                        ]
                    });
                });
        },
        renderNetWorth() {
            const el = this.$refs.netWorthChart; if (!el) return;
            const chart = this._initChart(el);
            if (!this.snapshots || !this.snapshots.length) {
                chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } });
                return;
            }
            const dates = this.snapshots.map(s => s.snapshot_date);
            const debtData = this.snapshots.map(s => s.total_debt);
            // Match cash to snapshot months
            const cashMap = {};
            (this.cashHistory || []).forEach(r => {
                const m = r.recorded_at ? r.recorded_at.substring(0, 7) : '';
                cashMap[m] = r.amount;
            });
            const cashData = dates.map(d => {
                const m = d.substring(0, 7);
                return cashMap[m] || 0;
            });
            const netWorthData = dates.map((d, i) => cashData[i] - debtData[i]);

            chart.setOption({
                tooltip: { trigger: 'axis', formatter: function(params) {
                    let s = '<b>' + params[0].axisValue + '</b><br/>';
                    params.forEach(p => { s += p.marker + ' ' + p.seriesName + ': ¥' + Math.abs(p.value).toLocaleString() + (p.value < 0 ? ' (负)' : ''); });
                    return s;
                }},
                grid: { left: 70, right: 20, top: 20, bottom: 30 },
                legend: { data: ['总负债', '总资产(现金)', '净资产'], textStyle: { color: '#888', fontSize: 11 }, top: 0 },
                xAxis: { type: 'category', data: dates, axisLabel: { color: '#888', fontSize: 10, rotate: 30 } },
                yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => axisUnit(v) }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                series: [
                    { name: '总负债', type: 'line', data: debtData, lineStyle: { color: '#e94560', width: 2 }, itemStyle: { color: '#e94560' }, symbol: 'circle', symbolSize: 4 },
                    { name: '总资产(现金)', type: 'line', data: cashData, lineStyle: { color: '#00d2a0', width: 2 }, itemStyle: { color: '#00d2a0' }, symbol: 'diamond', symbolSize: 4 },
                    { name: '净资产', type: 'line', data: netWorthData, lineStyle: { color: '#4facfe', width: 2 }, itemStyle: { color: '#4facfe' }, areaStyle: { color: 'rgba(79,172,254,0.1)' }, symbol: 'triangle', symbolSize: 4 },
                ]
            });
        }
    }
};

// ---- Persons ----
const PersonsPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>人员管理</h2><p>维护家庭成员信息，用于关联借贷、收入、支出等</p></div>
    <div class="section-card">
        <h3>{{ editing ? '编辑人员' : '添加人员' }}</h3>
        <div class="form-row">
            <div class="form-group"><label>姓名</label><input v-model="form.name" placeholder="请输入姓名"></div>
            <div class="form-group"><label>关系</label><select v-model="form.relation"><option value="本人">本人</option><option value="配偶">配偶</option><option value="父母">父母</option><option value="子女">子女</option></select></div>
        </div>
        <button class="btn btn-primary" @click="submit">{{ editing ? '保存修改' : '添加' }}</button>
        <button v-if="editing" class="btn btn-secondary" @click="cancelEdit" style="margin-left:8px">取消</button>
    </div>
    <div v-if="items.length > 0" style="margin-top:16px">
        <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/persons/' + id, { method: 'DELETE' }))" style="margin-bottom:8px">批量删除</button>
        <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>姓名</th><th>关系</th><th>操作</th></tr></thead>
            <tbody><tr v-for="p in items" :key="p.id">
                <td><input type="checkbox" :checked="selectedIds.includes(p.id)" @change="toggleSelect(p.id)"></td>
                <td>{{ p.id }}</td><td>{{ p.name }}</td><td><span class="tag blue">{{ p.relation }}</span></td>
                <td><button class="btn btn-secondary btn-xs" @click="openEdit(p)" style="margin-right:4px">编辑</button><button class="btn btn-danger btn-xs" @click="remove(p.id)">删除</button></td>
            </tr></tbody>
        </table>
    </div>
    <div v-else class="empty-state">暂无人员，请添加</div>
</div>`,
    data() { return { form: { name: '', relation: '本人' }, items: [], selectedIds: [], editing: null }; },
    async mounted() { await this.load(); },
    methods: {
        fmt,
        async load() { try { this.items = await api('/persons/'); } catch(e) { this.showToast(e.message, 'error'); } },
        openEdit(p) { this.editing = p; this.form = { name: p.name, relation: p.relation }; },
        cancelEdit() { this.editing = null; this.form = { name: '', relation: '本人' }; },
        async submit() {
            if (!this.form.name) return this.showToast('请输入姓名', 'error');
            if (this.editing) {
                try { await api('/persons/' + this.editing.id, { method: 'PATCH', body: JSON.stringify(this.form) }); this.showToast('修改成功'); this.cancelEdit(); await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            } else {
                try { await api('/persons/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('添加成功'); this.form = { name: '', relation: '本人' }; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/persons/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Platforms ----
const PlatformsPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>借贷平台</h2><p>管理借款来源平台（借呗、微粒贷、银行等）</p></div>
    <div class="section-card">
        <h3>{{ editing ? '编辑平台' : '添加平台' }}</h3>
        <div class="form-row">
            <div class="form-group"><label>平台名称</label><input v-model="form.name" placeholder="如：借呗"></div>
            <div class="form-group"><label>图标</label><input v-model="form.icon" placeholder="emoji 或文字"></div>
        </div>
        <div class="form-group"><label>描述</label><input v-model="form.description" placeholder="备注说明"></div>
        <button class="btn btn-primary" @click="submit">{{ editing ? '保存修改' : '添加' }}</button>
        <button v-if="editing" class="btn btn-secondary" @click="cancelEdit" style="margin-left:8px">取消</button>
    </div>
    <div v-if="items.length > 0" style="margin-top:16px">
        <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/platforms/' + id, { method: 'DELETE' }))" style="margin-bottom:8px">批量删除</button>
        <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>名称</th><th>图标</th><th>描述</th><th>操作</th></tr></thead>
            <tbody><tr v-for="p in items" :key="p.id">
                <td><input type="checkbox" :checked="selectedIds.includes(p.id)" @change="toggleSelect(p.id)"></td>
                <td>{{ p.id }}</td><td>{{ p.name }}</td><td>{{ p.icon }}</td><td style="color:#888">{{ p.description }}</td>
                <td><button class="btn btn-secondary btn-xs" @click="openEdit(p)" style="margin-right:4px">编辑</button><button class="btn btn-danger btn-xs" @click="remove(p.id)">删除</button></td>
            </tr></tbody>
        </table>
    </div>
    <div v-else class="empty-state">暂无平台，请添加</div>
</div>`,
    data() { return { form: { name: '', icon: '', description: '' }, items: [], selectedIds: [], editing: null }; },
    async mounted() { await this.load(); },
    methods: {
        async load() { try { this.items = await api('/platforms/'); } catch(e) { this.showToast(e.message, 'error'); } },
        openEdit(p) { this.editing = p; this.form = { name: p.name, icon: p.icon, description: p.description }; },
        cancelEdit() { this.editing = null; this.form = { name: '', icon: '', description: '' }; },
        async submit() {
            if (!this.form.name) return this.showToast('请输入平台名称', 'error');
            if (this.editing) {
                try { await api('/platforms/' + this.editing.id, { method: 'PATCH', body: JSON.stringify(this.form) }); this.showToast('修改成功'); this.cancelEdit(); await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            } else {
                try { await api('/platforms/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('添加成功'); this.form = { name: '', icon: '', description: '' }; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/platforms/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Loans ----
const LoansPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>借贷管理</h2><p>管理各平台借款及还款计划</p></div>
    <div class="filter-bar">
        <span class="filter-chip" :class="{ active: !filterPerson }" @click="filterPerson = null">全部</span>
        <span class="filter-chip" v-for="p in persons" :key="p.id" :class="{ active: filterPerson === p.id }" @click="filterPerson = p.id">{{ p.name }}</span>
    </div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增借款</button>
    <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/loans/' + id, { method: 'DELETE' }))" style="margin-bottom:12px;margin-left:8px">批量删除</button>
    <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>人员</th><th>平台</th><th>金额</th><th>利率</th><th>方式</th><th>总期数</th><th>已还</th><th>剩余</th><th>状态</th><th>操作</th></tr></thead>
        <tbody><tr v-for="l in filteredLoans" :key="l.id">
            <td><input type="checkbox" :checked="selectedIds.includes(l.id)" @change="toggleSelect(l.id)"></td>
            <td>{{ l.id }}</td><td>{{ l.person?.name || '-' }}</td><td>{{ l.platform?.name || '-' }}</td>
            <td>¥{{ fmt(l.amount) }}</td><td>{{ annualRateStr(l) }}</td>
            <td><span class="tag blue">{{ repayMethodLabel(l.repay_method) }}</span></td>
            <td>{{ l.periods }}</td>
            <td>{{ l.paid_periods || 0 }}</td>
            <td :style="{ color: (l.remaining_periods || 0) > 0 ? 'var(--yellow)' : 'var(--green)' }">{{ l.remaining_periods || 0 }}</td>
            <td><span :class="'tag ' + (l.status === 'active' ? 'green' : 'red')">{{ l.status === 'active' ? '还款中' : '已结清' }}</span></td>
            <td>
                <button class="btn btn-secondary btn-xs" @click="openEdit(l)" style="margin-right:4px">编辑</button>
                <button class="btn btn-secondary btn-xs" @click="viewRepayments(l)" style="margin-right:4px">还款计划</button>
                <button class="btn btn-danger btn-xs" @click="remove(l.id)">删除</button>
            </td>
        </tr></tbody>
    </table>
    <div v-if="filteredLoans.length === 0" class="empty-state">暂无借款记录</div>

    <!-- Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '编辑' : '新增' }}借款</h3>
            <div class="form-row">
                <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
                <div class="form-group"><label>平台</label><select v-model="form.platform_id"><option v-for="p in platforms" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            </div>
            <div class="form-group"><label>借款金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01" placeholder="0.00"></div>
            <div class="form-row">
                <div class="form-group" v-if="form.repay_method !== 'flexible'"><label>利率类型</label><select v-model="form.rate_type" @change="onRateTypeChange"><option value="monthly">月利率</option><option value="annual">年利率</option><option value="total_interest">总利息反推</option></select></div>
                <div class="form-group" v-if="form.rate_type === 'total_interest' && form.repay_method !== 'flexible'"><label>总利息金额</label><input v-model.number="form.total_interest" type="number" min="0" step="0.01" placeholder="总利息金额"></div>
                <div class="form-group" v-else-if="form.repay_method !== 'flexible'">
                        <label>利率 (%)</label>
                        <input v-model.number="form.rate" type="number" step="0.01" :placeholder="form.rate_type === 'monthly' ? '月利: 0.5 表示 0.5%' : '年利: 4.11 表示 4.11%'">
                    </div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>还款方式</label><select v-model="form.repay_method" @change="onRepayMethodChange"><option value="equal_installment">等额本息</option><option value="interest_first">先息后本</option><option value="bullet">到期还本付息</option><option value="flexible">无固定期限（个人借贷）</option></select></div>
                <div class="form-group"><label>总期数</label><input v-model.number="form.periods" type="number" min="0" placeholder="0 表示无固定期数"></div>
                <div class="form-group"><label>每月还款日</label><input v-model.number="form.repay_day" type="number" min="1" max="28" placeholder="留空为开始日"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>已还期数</label><input v-model.number="form.paid_periods" type="number" min="0" placeholder="0"></div>
                <div class="form-group"><label>开始日期</label><input v-model="form.start_date" type="date"></div>
            </div>
            <div class="form-group"><label>结束日期</label><input v-model="form.end_date" type="date"></div>
            <div class="form-group"><label>备注</label><input v-model="form.note" placeholder="借款用途等"></div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="submit">{{ editing ? '保存修改' : '确认创建' }}</button>
            </div>
        </div>
    </div>

    <!-- Repayments Modal -->
    <div v-if="repayLoan" class="modal-overlay" @click.self="repayLoan = null">
        <div class="modal" style="width:780px"><h3>还款计划 — {{ repayLoan.person?.name }} / {{ repayLoan.platform?.name }} (¥{{ fmt(repayLoan.amount) }})
            <button class="btn btn-secondary btn-sm" @click="regeneratePlan" style="margin-left:12px">重新计算</button></h3>
            <table class="data-table"><thead><tr><th>期数</th><th>到期日</th><th>本金</th><th>利息</th><th>总还款</th><th>剩余还款</th><th>状态</th><th>操作</th></tr></thead>
                <tbody><tr v-for="(r, idx) in repayments" :key="r.id">
                    <td>{{ r.period_no }}</td><td>{{ r.due_date }}</td><td>¥{{ fmt(r.principal) }}</td><td>¥{{ fmt(r.interest) }}</td><td>¥{{ fmt(r.total_amount) }}</td>
                    <td style="color:var(--yellow)">¥{{ fmt(remainingFrom(idx)) }}</td>
                    <td><span :class="'tag ' + (r.status === 'paid' ? 'green' : 'yellow')">{{ r.status === 'paid' ? '已还' : '待还' }}</span></td>
                    <td><button v-if="r.status === 'pending'" class="btn btn-secondary btn-xs" @click="pay(r.id)">标记已还</button><span v-else style="color:#888;font-size:11px">{{ r.paid_date ? r.paid_date.split('T')[0] : '-' }}</span></td>
                </tr></tbody>
            </table>
            <div style="margin-top:12px;text-align:right"><button class="btn btn-secondary" @click="repayLoan = null">关闭</button></div>
        </div>
    </div>
</div>`,
    data() {
        return {
            loans: [], persons: [], platforms: [], repayments: [], filterPerson: null,
            showModal: false, editing: null, repayLoan: null,
            form: {
                person_id: 1, platform_id: 1, amount: 0, rate: 0, rate_type: 'monthly',
                total_interest: null, repay_method: 'equal_installment',
                periods: 12, paid_periods: 0, start_date: todayStr(), end_date: null, note: ''
            }
        };
    },
    async mounted() {
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.platforms = await api('/platforms/'); } catch(e) {}
        try { this.loans = await api('/loans/'); } catch(e) {}
        if (this.persons.length) this.form.person_id = this.persons[0].id;
        if (this.platforms.length) this.form.platform_id = this.platforms[0].id;
    },
    computed: {
        filteredLoans() { return this.filterPerson ? this.loans.filter(l => l.person_id === this.filterPerson) : this.loans; }
    },
    methods: {
        fmt,
        rateTypeLabel(t) { const m = { monthly: '月利率', annual: '年利率', total_interest: '总利息反推' }; return m[t] || t; },
        annualRateStr(l) {
            if (l.rate_type === 'total_interest') return '总利息 ¥' + fmt(l.rate);
            if (l.rate_type === 'annual') return (l.rate * 100).toFixed(2) + '%';
            return (l.rate * 12 * 100).toFixed(2) + '%';
        },
        repayMethodLabel(m) { const mp = { equal_installment: '等额本息', interest_first: '先息后本', bullet: '到期还本', flexible: '无固定期' }; return mp[m] || m; },
        onRateTypeChange() { if (this.form.rate_type === 'total_interest') { this.form.rate = 0; } },
        onRepayMethodChange() { if (this.form.repay_method === 'flexible') { this.form.periods = 0; this.form.rate = 0; } else if (!this.form.periods) { this.form.periods = 12; } },
        openCreate() {
            this.editing = null;
            this.form = {
                person_id: this.persons[0]?.id || 1, platform_id: this.platforms[0]?.id || 1,
                amount: 0, rate: 0, rate_type: 'monthly', total_interest: null,
                repay_method: 'equal_installment', periods: 12, paid_periods: 0,
                repay_day: null, start_date: todayStr(), end_date: null, note: ''
            };
            this.showModal = true;
        },
        openEdit(l) {
            this.editing = l;
            // 自动计算已还期数 = 当前月份 - 开始月份
            const start = new Date(l.start_date);
            const now = new Date();
            const autoPaid = Math.max(0, (now.getFullYear() - start.getFullYear()) * 12 + (now.getMonth() - start.getMonth()));
            this.form = {
                person_id: l.person_id, platform_id: l.platform_id,
                amount: l.amount,
                rate: l.rate_type === 'total_interest' ? 0 : +(l.rate * 100).toFixed(4),
                rate_type: l.rate_type,
                total_interest: l.rate_type === 'total_interest' ? l.rate : null,
                repay_method: l.repay_method, periods: l.periods, paid_periods: Math.max(l.paid_periods || 0, autoPaid),
                repay_day: l.repay_day, start_date: l.start_date, end_date: l.end_date, note: l.note || ''
            };
            this.showModal = true;
        },
        async submit() {
            if (!this.form.amount) return this.showToast('请填写金额', 'error');
            if (this.form.repay_method !== 'flexible' && !this.form.periods) return this.showToast('请填写期数', 'error');
            if (this.editing) {
                const body = { ...this.form };
                if (body.rate_type === 'total_interest') {
                    if (!body.total_interest) return this.showToast('请填写总利息金额', 'error');
                    body.rate = body.total_interest;
                } else {
                    body.rate = body.rate / 100;
                }
                delete body.total_interest;
                if (!body.end_date) delete body.end_date;
                try {
                    await api('/loans/' + this.editing.id, { method: 'PATCH', body: JSON.stringify(body) });
                    // Auto-regenerate plan if key params changed
                    const changed = body.rate !== this.editing.rate || body.rate_type !== this.editing.rate_type ||
                        body.amount !== this.editing.amount || body.periods !== this.editing.periods ||
                        body.repay_method !== this.editing.repay_method || body.start_date !== this.editing.start_date;
                    if (changed) {
                        await api('/loans/' + this.editing.id + '/regenerate-plan', { method: 'POST' });
                    }
                    this.showToast('借款已更新');
                    this.showModal = false;
                    this.loans = await api('/loans/');
                } catch(e) { this.showToast(e.message, 'error'); }
            } else {
                const body = { ...this.form };
                if (body.rate_type === 'total_interest') {
                    if (!body.total_interest) return this.showToast('请填写总利息金额', 'error');
                    body.rate = body.total_interest;
                } else {
                    body.rate = body.rate / 100;
                }
                delete body.total_interest;
                if (!body.end_date) delete body.end_date;
                try {
                    const loan = await api('/loans/', { method: 'POST', body: JSON.stringify(body) });
                    if (this.form.paid_periods > 0) {
                        const rps = await api('/loans/' + loan.id + '/repayments');
                        for (const rp of rps) {
                            if (rp.period_no <= this.form.paid_periods && rp.status === 'pending') {
                                await api('/loans/repayments/' + rp.id + '/pay', { method: 'PATCH' });
                            }
                        }
                    }
                    this.showToast('借款创建成功，还款计划已自动生成');
                    this.showModal = false;
                    this.loans = await api('/loans/');
                } catch(e) { this.showToast(e.message, 'error'); }
            }
        },
        async viewRepayments(loan) {
            this.repayLoan = loan;
            try { this.repayments = await api('/loans/' + loan.id + '/repayments'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async pay(rpId) {
            try { await api('/loans/repayments/' + rpId + '/pay', { method: 'PATCH' }); this.showToast('已标记还款'); this.repayments = await api('/loans/' + this.repayLoan.id + '/repayments'); this.loans = await api('/loans/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async regeneratePlan() {
            if (!confirm('将根据当前利率重新计算所有还款计划，已还期数会保留。确定继续？')) return;
            try {
                this.repayments = await api('/loans/' + this.repayLoan.id + '/regenerate-plan', { method: 'POST' });
                this.showToast('还款计划已重新计算');
                this.loans = await api('/loans/');
            } catch(e) { this.showToast(e.message, 'error'); }
        },
        remainingFrom(idx) {
            let sum = 0;
            for (let i = idx; i < this.repayments.length; i++) {
                if (this.repayments[i].status === 'pending') sum += this.repayments[i].total_amount;
            }
            return sum;
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/loans/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } },
        async load() { try { this.loans = await api('/loans/'); } catch(e) {} }
    }
};

// ---- POS Swipes ----
const PosPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>POS 刷卡</h2><p>管理 POS 机刷卡记录，自动计算手续费</p></div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增刷卡</button>
    <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/pos-swipes/' + id, { method: 'DELETE' }))" style="margin-bottom:12px;margin-left:8px">批量删除</button>
    <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>人员</th><th>金额</th><th>费率</th><th>手续费</th><th>银行卡</th><th>POS机</th><th>刷卡时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="s in items" :key="s.id">
            <td><input type="checkbox" :checked="selectedIds.includes(s.id)" @change="toggleSelect(s.id)"></td>
            <td>{{ s.id }}</td><td>{{ s.person?.name || '-' }}</td>
            <td :style="{ color: s.amount < 0 ? 'var(--green)' : '' }">¥{{ fmt(Math.abs(s.amount)) }}</td>
            <td>{{ s.amount < 0 ? '-' : (s.fee_rate * 10000).toFixed(1) + '元/万' }}</td><td>¥{{ fmt(s.fee) }}</td>
            <td>{{ s.bank_card }}</td><td>{{ s.pos_machine }}</td><td>{{ fmtDate(s.swipe_date) }}</td>
            <td><button class="btn btn-secondary btn-xs" @click="openEdit(s)" style="margin-right:4px">编辑</button><button class="btn btn-danger btn-xs" @click="remove(s.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="items.length === 0" class="empty-state">暂无刷卡记录</div>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '编辑' : '新增' }}刷卡记录</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-row" style="align-items:flex-end">
                <div class="form-group"><label>刷卡金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01" placeholder="0.00"></div>
                <div class="form-group" style="margin-bottom:12px"><label style="display:flex;align-items:center;gap:6px;cursor:pointer"><input type="checkbox" v-model="form.is_refund" style="width:auto"> 退款</label></div>
            </div>
            <div class="form-group" v-if="!form.is_refund"><label>费率 (留空使用默认 60元/万)</label><input v-model.number="form.fee_rate" type="number" step="0.0001" placeholder="0.006 = 60元/万"></div>
            <div class="form-row">
                <div class="form-group"><label>银行卡（关联信用卡额度）</label><select v-model="form.card_id" @change="onCardSelect"><option :value="null">-- 请选择 --</option><option v-for="c in cards" :key="c.id" :value="c.id">{{ c.bank }} 尾号{{ c.card_number_last4 }}（{{ c.person?.name || '' }} | 已用 ¥{{ fmt(c.current_balance) }}）</option></select></div>
                <div class="form-group"><label>POS机</label><input v-model="form.pos_machine" placeholder="如：拉卡拉"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>刷卡时间</label><input v-model="form.swipe_date" type="datetime-local"></div>
                <div class="form-group"><label>备注</label><input v-model="form.note" placeholder="如：资金周转"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="submit">{{ editing ? '保存修改' : '确认' }}</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return {
            items: [], persons: [], cards: [], showModal: false, editing: null, selectedIds: [],
            form: { person_id: 1, card_id: null, amount: 0, fee_rate: null, bank_card: '', pos_machine: '', swipe_date: nowStr(), note: '' }
        };
    },
    async mounted() { await this.load(); },
    methods: {
        fmt, fmtDate,
        async load() {
            try { this.persons = await api('/persons/'); } catch(e) {}
            try { this.cards = await api('/credit-cards/'); } catch(e) {}
            try { this.items = await api('/pos-swipes/'); } catch(e) {}
            if (this.persons.length) this.form.person_id = this.persons[0].id;
        },
        onCardSelect() {
            const card = this.cards.find(c => c.id === this.form.card_id);
            this.form.bank_card = card ? (card.bank + ' 尾号' + card.card_number_last4) : '';
        },
        openCreate() {
            this.editing = null;
            this.form = { person_id: this.persons[0]?.id || 1, card_id: null, amount: 0, fee_rate: null, bank_card: '', pos_machine: '', swipe_date: nowStr(), note: '', is_refund: false };
            this.showModal = true;
        },
        openEdit(s) {
            this.editing = s;
            this.form = {
                person_id: s.person_id, card_id: s.card_id || null,
                amount: Math.abs(s.amount), fee_rate: s.amount < 0 ? 0 : s.fee_rate,
                bank_card: s.bank_card || '',
                pos_machine: s.pos_machine, swipe_date: s.swipe_date?.replace?.(' ', 'T') || nowStr(), note: s.note || '',
                is_refund: s.amount < 0
            };
            this.showModal = true;
        },
        async submit() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            const body = { ...this.form };
            if (body.is_refund) { body.amount = -Math.abs(body.amount); body.fee_rate = 0; }
            delete body.is_refund;
            if (!body.card_id) body.card_id = null;
            if (body.fee_rate === '' || body.fee_rate === null || body.fee_rate === undefined) delete body.fee_rate;
            if (this.editing) {
                try { await api('/pos-swipes/' + this.editing.id, { method: 'PATCH', body: JSON.stringify(body) }); this.showToast('刷卡记录已更新'); this.showModal = false; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            } else {
                try { await api('/pos-swipes/', { method: 'POST', body: JSON.stringify(body) }); this.showToast('刷卡记录已添加'); this.showModal = false; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/pos-swipes/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Credit Cards ----
const CreditCardsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>信用卡管理</h2></div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:16px">+ 新增信用卡</button>

    <div class="section-card" v-for="c in items" :key="c.id" style="margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <div>
                <strong style="font-size:15px">{{ c.bank }}</strong>
                <span style="color:#888;margin-left:8px;font-size:12px">尾号{{ c.card_number_last4 }}</span>
                <span style="color:#888;margin-left:8px;font-size:12px">({{ c.person?.name }})</span>
                <span :class="'tag ' + (c.status === 'active' ? 'green' : 'red')" style="margin-left:8px">{{ c.status === 'active' ? '正常' : '停用' }}</span>
            </div>
            <div style="display:flex;gap:4px">
                <button class="btn btn-secondary btn-xs" @click="openEdit(c)">编辑信息</button>
                <button class="btn btn-secondary btn-xs" @click="toggleBills(c)">{{ viewingCard === c.id ? '收起账单' : '查看账单' }}</button>
                <button class="btn btn-danger btn-xs" @click="remove(c.id)">删除</button>
            </div>
        </div>
        <div style="font-size:11px;color:#888;margin-top:6px">
            额度 ¥{{ fmt(c.credit_limit) }} · 账单日 {{ c.bill_day }}号 · 还款日 {{ c.due_day }}号
            <span v-if="cardBills[c.id] && cardBills[c.id].length" style="margin-left:8px">
                · 本期账单: <strong :style="{ color: cardBills[c.id][0].status === 'paid' ? 'var(--green)' : 'var(--red)' }">¥{{ fmt(cardBills[c.id][0].bill_amount) }}</strong>
                <span :class="'tag ' + (cardBills[c.id][0].status === 'paid' ? 'green' : cardBills[c.id][0].status === 'partial' ? 'yellow' : cardBills[c.id][0].status === 'overdue' ? 'red' : 'blue')" style="margin-left:4px">{{ billStatusLabel(cardBills[c.id][0].status) }}</span>
            </span>
        </div>

        <div v-if="viewingCard === c.id" style="margin-top:12px">
            <div v-if="cardBills[c.id] && cardBills[c.id].length" style="overflow-x:auto">
                <table class="data-table"><thead><tr><th>账单月份</th><th>周期</th><th>还款日</th><th>账单金额</th><th>已还</th><th>未还</th><th>利息</th><th>手续费</th><th>状态</th><th>操作</th></tr></thead>
                    <tbody><tr v-for="b in cardBills[c.id]" :key="b.id">
                        <td>{{ b.bill_month }}</td>
                        <td style="font-size:10px;color:#888">{{ b.bill_start }} ~ {{ b.bill_end }}</td>
                        <td>{{ b.due_date }}</td>
                        <td>\u00a5{{ fmt(b.bill_amount) }}</td>
                        <td style="color:var(--green)">\u00a5{{ fmt(b.paid_amount) }}</td>
                        <td :style="{ color: (b.bill_amount - b.paid_amount) > 0 ? 'var(--red)' : 'var(--green)' }">\u00a5{{ fmt(Math.max(0, b.bill_amount - b.paid_amount)) }}</td>
                        <td>\u00a5{{ fmt(b.interest) }}</td>
                        <td>\u00a5{{ fmt(b.fee) }}</td>
                        <td><span :class="'tag ' + (b.status === 'paid' ? 'green' : b.status === 'partial' ? 'yellow' : b.status === 'overdue' ? 'red' : 'blue')">{{ billStatusLabel(b.status) }}</span></td>
                        <td>
                            <button v-if="b.status !== 'paid'" class="btn btn-secondary btn-xs" @click="payFull(b.id)" style="margin-right:2px">全额还</button>
                            <button v-if="b.status === 'unpaid' || b.status === 'overdue'" class="btn btn-secondary btn-xs" @click="payMinimum(b.id)" style="margin-right:2px">最低还</button>
                            <button v-if="b.status === 'paid' || b.status === 'partial'" class="btn btn-secondary btn-xs" @click="undoPayment(b.id)" style="margin-right:2px">撤销</button>
                            <button class="btn btn-secondary btn-xs" @click="openBillEdit(b)">录入</button>
                        </td>
                    </tr></tbody>
                </table>
            </div>
            <div v-else style="padding:12px;color:#888;font-size:12px">暂无账单（当期账单将自动生成）</div>
        </div>
    </div>
    <div v-if="items.length === 0" class="empty-state">暂无信用卡</div>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '编辑' : '新增' }}信用卡</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-row">
                <div class="form-group"><label>银行</label><input v-model="form.bank" placeholder="如：招商银行"></div>
                <div class="form-group"><label>卡号后四位</label><input v-model="form.card_number_last4" maxlength="4" placeholder="8823"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>信用额度</label><input v-model.number="form.credit_limit" type="number" min="0" placeholder="50000"></div>
                <div class="form-group"><label>透支年利率</label><input v-model.number="form.interest_rate" type="number" step="0.0001" min="0" placeholder="0.1825"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>账单日</label><input v-model.number="form.bill_day" type="number" min="1" max="28" placeholder="5"></div>
                <div class="form-group"><label>还款日</label><input v-model.number="form.due_day" type="number" min="1" max="28" placeholder="25"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="editing ? update() : create()">{{ editing ? '保存' : '创建' }}</button>
            </div>
        </div>
    </div>

    <div v-if="billEditModal.show" class="modal-overlay" @click.self="billEditModal.show = false">
        <div class="modal"><h3>录入账单 \u2014 {{ billEditModal.bill_month }}</h3>
            <div class="form-row">
                <div class="form-group"><label>账单金额</label><input v-model.number="billForm.bill_amount" type="number" min="0" step="0.01"></div>
                <div class="form-group"><label>实际还款</label><input v-model.number="billForm.paid_amount" type="number" min="0" step="0.01"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>本期利息</label><input v-model.number="billForm.interest" type="number" min="0" step="0.01"></div>
                <div class="form-group"><label>本期手续费</label><input v-model.number="billForm.fee" type="number" min="0" step="0.01"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>账单周期开始</label><input v-model="billForm.bill_start" type="date"></div>
                <div class="form-group"><label>账单周期结束</label><input v-model="billForm.bill_end" type="date"></div>
            </div>
            <div class="form-group"><label>还款截止日</label><input v-model="billForm.due_date" type="date"></div>
            <div class="form-group"><label>备注</label><input v-model="billForm.note"></div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="billEditModal.show = false">取消</button>
                <button class="btn btn-primary" @click="saveBill">保存</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], persons: [], cardBills: {}, viewingCard: null, showModal: false, editing: null, form: { person_id: 1, bank: '', card_number_last4: '', credit_limit: 0, interest_rate: 0.1825, bill_day: 1, due_day: 25 }, billEditModal: { show: false, billId: null, cardId: null, bill_month: '' }, billForm: { bill_amount: 0, paid_amount: 0, interest: 0, fee: 0, bill_start: '', bill_end: '', due_date: '', note: '' } };
    },
    async mounted() { await this.load(); },
    methods: {
        fmt,
        billStatusLabel(s) { const m = { unpaid: '未还', partial: '部分还', paid: '已还清', overdue: '逾期' }; return m[s] || s; },
        async load() {
            try { this.persons = await api('/persons/'); } catch(e) {}
            try { this.items = await api('/credit-cards/'); } catch(e) {}
            if (this.persons.length) this.form.person_id = this.persons[0].id;
        },
        async toggleBills(c) {
            if (this.viewingCard === c.id) { this.viewingCard = null; return; }
            this.viewingCard = c.id;
            if (!this.cardBills[c.id]) {
                try { this.cardBills[c.id] = await api('/credit-card-bills/?card_id=' + c.id); } catch(e) {}
            }
        },
        async payFull(billId) {
            try { await api('/credit-card-bills/' + billId + '/pay-full', { method: 'POST' }); this.showToast('已标记全额还款'); await this.refreshBills(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async payMinimum(billId) {
            try { await api('/credit-card-bills/' + billId + '/pay-minimum', { method: 'POST' }); this.showToast('已标记最低还款'); await this.refreshBills(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async undoPayment(billId) {
            if (!confirm('确定撤销还款？撤销后该账单恢复为未还状态。')) return;
            try { await api('/credit-card-bills/' + billId + '/undo-payment', { method: 'POST' }); this.showToast('还款已撤销'); await this.refreshBills(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        openBillEdit(b) {
            this.billEditModal = { show: true, billId: b.id, cardId: b.card_id, bill_month: b.bill_month };
            this.billForm = { bill_amount: b.bill_amount, paid_amount: b.paid_amount, interest: b.interest, fee: b.fee, bill_start: b.bill_start, bill_end: b.bill_end, due_date: b.due_date, note: b.note || '' };
        },
        async saveBill() {
            try {
                await api('/credit-card-bills/' + this.billEditModal.billId, { method: 'PATCH', body: JSON.stringify(this.billForm) });
                this.showToast('账单已保存'); this.billEditModal.show = false;
                await this.refreshBills();
            } catch(e) { this.showToast(e.message, 'error'); }
        },
        async refreshBills() {
            const cid = this.viewingCard || this.billEditModal.cardId;
            if (cid) try { this.cardBills[cid] = await api('/credit-card-bills/?card_id=' + cid); } catch(e) {}
        },
        openCreate() { this.editing = null; this.form = { person_id: this.persons[0]?.id || 1, bank: '', card_number_last4: '', credit_limit: 0, interest_rate: 0.1825, bill_day: 1, due_day: 25 }; this.showModal = true; },
        openEdit(c) { this.editing = c; this.form = { person_id: c.person_id, bank: c.bank, card_number_last4: c.card_number_last4, credit_limit: c.credit_limit, interest_rate: c.interest_rate || 0.1825, bill_day: c.bill_day, due_day: c.due_day }; this.showModal = true; },
        async create() {
            if (!this.form.bank || !this.form.card_number_last4) return this.showToast('请填写银行和卡号', 'error');
            try { await api('/credit-cards/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('信用卡已添加'); this.showModal = false; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async update() {
            try {
                await api('/credit-cards/' + this.editing.id, { method: 'PATCH', body: JSON.stringify({ credit_limit: this.form.credit_limit, interest_rate: this.form.interest_rate, bill_day: this.form.bill_day, due_day: this.form.due_day }) });
                this.showToast('已更新'); this.showModal = false; await this.load();
            } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/credit-cards/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Card Transactions ----
const CardTransactionsPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>信用卡消费/还款</h2><p>记录信用卡消费与还款明细，消费自动计入已用额度，还款自动扣减</p></div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增记录</button>
    <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/card-transactions/' + id, { method: 'DELETE' }))" style="margin-bottom:12px;margin-left:8px">批量删除</button>
    <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>人员</th><th>信用卡</th><th>类型</th><th>金额</th><th>描述</th><th>时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="t in items" :key="t.id">
            <td><input type="checkbox" :checked="selectedIds.includes(t.id)" @change="toggleSelect(t.id)"></td>
            <td>{{ t.id }}</td><td>{{ t.person?.name || '-' }}</td><td>{{ t.card?.bank }} {{ t.card?.card_number_last4 }}</td>
            <td><span :class="'tag ' + (t.trans_type === '还款' ? 'green' : 'red')">{{ t.trans_type }}</span></td>
            <td :style="{ color: t.trans_type === '还款' ? 'var(--green)' : 'var(--red)' }">¥{{ fmt(t.amount) }}</td>
            <td>{{ t.description }} <span v-if="(t.description||'').startsWith('[系统自动]')" class="tag yellow" style="font-size:9px">自动</span></td><td>{{ fmtDate(t.trans_date) }}</td>
            <td><button class="btn btn-secondary btn-xs" @click="openEdit(t)" style="margin-right:4px">编辑</button><button class="btn btn-danger btn-xs" @click="remove(t.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="items.length === 0" class="empty-state">暂无记录</div>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '编辑' : '新增' }}记录</h3>
            <div class="form-group"><label>类型</label><select v-model="form.trans_type"><option value="消费">消费</option><option value="还款">还款</option></select></div>
            <div class="form-group"><label>信用卡</label><select v-model="form.card_id"><option v-for="c in cards" :key="c.id" :value="c.id">{{ c.bank }} 尾号{{ c.card_number_last4 }} ({{ c.person?.name }})</option></select></div>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01" placeholder="0.00"></div>
            <div class="form-row">
                <div class="form-group"><label>描述</label><input v-model="form.description" placeholder="说明"></div>
                <div class="form-group"><label>时间</label><input v-model="form.trans_date" type="datetime-local"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="submit">{{ editing ? '保存修改' : '确认' }}</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], cards: [], persons: [], showModal: false, editing: null, selectedIds: [], form: { card_id: 1, person_id: 1, amount: 0, trans_type: '消费', description: '', trans_date: nowStr() } };
    },
    async mounted() {
        try { this.cards = await api('/credit-cards/'); } catch(e) {}
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.items = await api('/card-transactions/'); } catch(e) {}
        if (this.cards.length) this.form.card_id = this.cards[0].id;
        if (this.persons.length) this.form.person_id = this.persons[0].id;
    },
    methods: {
        fmt, fmtDate,
        openCreate() {
            this.editing = null;
            this.form = { card_id: this.cards[0]?.id || 1, person_id: this.persons[0]?.id || 1, amount: 0, trans_type: '消费', description: '', trans_date: nowStr() };
            this.showModal = true;
        },
        openEdit(t) {
            this.editing = t;
            this.form = { card_id: t.card_id, person_id: t.person_id, amount: t.amount, trans_type: t.trans_type || '消费', description: t.description || '', trans_date: t.trans_date?.replace?.(' ', 'T') || nowStr() };
            this.showModal = true;
        },
        async submit() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            if (this.editing) {
                try { await api('/card-transactions/' + this.editing.id, { method: 'PATCH', body: JSON.stringify(this.form) }); this.showToast('记录已更新'); this.showModal = false; this.items = await api('/card-transactions/'); } catch(e) { this.showToast(e.message, 'error'); }
            } else {
                try { await api('/card-transactions/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('记录已添加'); this.showModal = false; this.items = await api('/card-transactions/'); } catch(e) { this.showToast(e.message, 'error'); }
            }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/card-transactions/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/card-transactions/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Installments ----
const InstallmentsPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>分期管理</h2><p>管理信用卡分期业务</p></div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增分期</button>
    <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/card-installments/' + id, { method: 'DELETE' }))" style="margin-bottom:12px;margin-left:8px">批量删除</button>
    <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>人员</th><th>信用卡</th><th>金额</th><th>总期数</th><th>每期费率</th><th>年化利率</th><th>每期还款</th><th>已还</th><th>剩余期数</th><th>剩余还款总额</th><th>操作</th></tr></thead>
        <tbody><tr v-for="i in items" :key="i.id">
            <td><input type="checkbox" :checked="selectedIds.includes(i.id)" @change="toggleSelect(i.id)"></td>
            <td>{{ i.id }}</td><td>{{ i.person?.name || '-' }}</td><td>{{ i.card?.bank || i.card_id }}</td>
            <td>¥{{ fmt(i.amount) }}</td><td>{{ i.periods }}</td><td>{{ (i.period_rate * 100).toFixed(2) }}%</td>
            <td><span class="tag yellow">{{ i.annual_rate ? (i.annual_rate * 100).toFixed(2) + '%' : '-' }}</span></td>
            <td>¥{{ fmt(i.period_total) }}</td><td>{{ i.paid_periods }}</td>
            <td :style="{ color: (i.remaining_periods || 0) > 0 ? 'var(--yellow)' : 'var(--green)' }">{{ i.remaining_periods || 0 }}</td>
            <td :style="{ color: 'var(--red)' }">¥{{ fmt((i.remaining_periods || 0) * i.period_total) }}</td>
            <td><button class="btn btn-secondary btn-xs" @click="openEdit(i)" style="margin-right:4px">编辑</button><button class="btn btn-secondary btn-xs" @click="payPeriod(i)" style="margin-right:4px">还一期</button><button class="btn btn-danger btn-xs" @click="remove(i.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="items.length === 0" class="empty-state">暂无分期记录</div>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '编辑' : '新增' }}分期</h3>
            <div class="form-group"><label>信用卡</label><select v-model="form.card_id"><option v-for="c in cards" :key="c.id" :value="c.id">{{ c.bank }} 尾号{{ c.card_number_last4 }}</option></select></div>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>分期金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01" placeholder="0.00"></div>
            <div class="form-group"><label>期数</label><input v-model.number="form.periods" type="number" min="1" placeholder="12"></div>
            <div class="form-group"><label>费率输入方式</label><select v-model="form.rate_type" @change="form.rate_value = 0"><option value="period_rate">每期手续费率 (%)</option><option value="annual_rate">年化利率 (%)</option><option value="total_fee">总手续费 (元)</option></select></div>
            <div class="form-group">
                <label>{{ form.rate_type === 'period_rate' ? '每期费率（如 0.6 表示 0.6%）' : form.rate_type === 'annual_rate' ? '年化利率（如 13 表示 13%）' : '总手续费金额（元）' }}</label>
                <input v-model.number="form.rate_value" type="number" step="0.01" min="0" placeholder="0">
            </div>
            <div class="form-row">
                <div class="form-group"><label>开始日期</label><input v-model="form.start_date" type="date"></div>
                <div class="form-group"><label>备注</label><input v-model="form.note" placeholder="如：消费分期"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="submit">{{ editing ? '保存修改' : '确认创建' }}</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], cards: [], persons: [], showModal: false, editing: null, selectedIds: [], form: { card_id: 1, person_id: 1, amount: 0, periods: 12, rate_type: 'period_rate', rate_value: 0, start_date: todayStr(), note: '' } };
    },
    async mounted() {
        try { this.cards = await api('/credit-cards/'); } catch(e) {}
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.items = await api('/card-installments/'); } catch(e) {}
        if (this.cards.length) this.form.card_id = this.cards[0].id;
        if (this.persons.length) this.form.person_id = this.persons[0].id;
    },
    methods: {
        fmt,
        openCreate() {
            this.editing = null;
            this.form = { card_id: this.cards[0]?.id || 1, person_id: this.persons[0]?.id || 1, amount: 0, periods: 12, rate_type: 'period_rate', rate_value: 0, start_date: todayStr(), note: '' };
            this.showModal = true;
        },
        openEdit(inst) {
            this.editing = inst;
            this.form = { ...inst, rate_type: inst.period_rate ? 'period_rate' : 'annual_rate', rate_value: inst.period_rate ? inst.period_rate * 100 : (inst.annual_rate || 0) * 100 };
            this.showModal = true;
        },
        async submit() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            if (!this.form.rate_value && this.form.rate_value !== 0) return this.showToast('请输入费率', 'error');
            const body = { ...this.form };
            if (body.rate_type === 'period_rate' || body.rate_type === 'annual_rate') {
                body.rate_value = body.rate_value / 100;
            }
            if (this.editing) {
                delete body.id; delete body.card; delete body.person;
                try { await api('/card-installments/' + this.editing.id, { method: 'PATCH', body: JSON.stringify(body) }); this.showToast('分期已更新'); this.showModal = false; this.items = await api('/card-installments/'); } catch(e) { this.showToast(e.message, 'error'); }
            } else {
                try { await api('/card-installments/', { method: 'POST', body: JSON.stringify(body) }); this.showToast('分期已创建'); this.showModal = false; this.items = await api('/card-installments/'); } catch(e) { this.showToast(e.message, 'error'); }
            }
        },
        async payPeriod(inst) {
            try { await api('/card-installments/' + inst.id + '/pay-period', { method: 'PATCH' }); this.showToast('已还一期'); this.items = await api('/card-installments/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/card-installments/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/card-installments/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Mortgages ----
const MortgagesPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>房贷管理</h2></div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增房贷</button>
    <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/mortgages/' + id, { method: 'DELETE' }))" style="margin-bottom:12px;margin-left:8px">批量删除</button>
    <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>人员</th><th>银行</th><th>房产</th><th>总金额</th><th>剩余本金</th><th>年利率</th><th>月供</th><th>状态</th><th>操作</th></tr></thead>
        <tbody><tr v-for="m in items" :key="m.id">
            <td><input type="checkbox" :checked="selectedIds.includes(m.id)" @change="toggleSelect(m.id)"></td>
            <td>{{ m.id }}</td><td>{{ m.person?.name || '-' }}</td><td>{{ m.bank }}</td><td>{{ m.house_name }}</td>
            <td>¥{{ fmt(m.total_amount) }}</td><td :style="{ color: 'var(--red)' }">¥{{ fmt(m.remaining_principal) }}</td>
            <td>{{ (m.rate * 100).toFixed(2) }}%</td><td>¥{{ fmt(m.monthly_payment) }}</td>
            <td><span :class="'tag ' + (m.status === 'active' ? 'green' : 'red')">{{ m.status === 'active' ? '还款中' : '已结清' }}</span></td>
            <td><button class="btn btn-secondary btn-xs" @click="openEdit(m)" style="margin-right:4px">更新本金</button><button class="btn btn-secondary btn-xs" @click="openPrepay(m)" style="margin-right:4px">提前还</button><button class="btn btn-danger btn-xs" @click="remove(m.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="items.length === 0" class="empty-state">暂无房贷</div>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '更新剩余本金' : '新增房贷' }}</h3>
            <template v-if="!editing">
                <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
                <div class="form-row">
                    <div class="form-group"><label>银行</label><input v-model="form.bank" placeholder="如：中国银行"></div>
                    <div class="form-group"><label>房产名称</label><input v-model="form.house_name" placeholder="如：阳光花园 3-1502"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>贷款总额</label><input v-model.number="form.total_amount" type="number" min="0" placeholder="0"></div>
                    <div class="form-group"><label>剩余本金</label><input v-model.number="form.remaining_principal" type="number" min="0" placeholder="0"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>年利率</label><input v-model.number="form.rate" type="number" step="0.0001" placeholder="0.04 = 4%"></div>
                    <div class="form-group"><label>月供</label><input v-model.number="form.monthly_payment" type="number" min="0" placeholder="0"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>开始日期</label><input v-model="form.start_date" type="date"></div>
                    <div class="form-group"><label>结束日期</label><input v-model="form.end_date" type="date"></div>
                </div>
                <div class="form-group"><label>总期数</label><input v-model.number="form.total_periods" type="number" min="1" placeholder="360"></div>
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                    <button class="btn btn-secondary" @click="showModal = false">取消</button>
                    <button class="btn btn-primary" @click="create">确认</button>
                </div>
            </template>
            <template v-else>
                <div class="form-group"><label>剩余本金</label><input v-model.number="editPrincipal" type="number" min="0"></div>
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                    <button class="btn btn-secondary" @click="showModal = false">取消</button>
                    <button class="btn btn-primary" @click="updatePrincipal">保存</button>
                </div>
            </template>
        </div>
    </div>
    <!-- 提前还款计算 -->
    <div v-if="prepayModal.show" class="modal-overlay" @click.self="prepayModal.show = false">
        <div class="modal"><h3>提前还款计算 — {{ prepayModal.bank }} {{ prepayModal.house }}</h3>
            <div style="font-size:12px;color:#888;margin-bottom:12px">剩余本金 ¥{{ fmt(prepayModal.principal) }} · 年利率 {{ (prepayModal.rate * 100).toFixed(2) }}% · 月供 ¥{{ fmt(prepayModal.payment) }}</div>
            <div class="form-group"><label>提前还款金额</label><input v-model.number="prepayModal.amount" type="number" min="0" step="1000" placeholder="输入金额"></div>
            <div v-if="prepayModal.amount > 0" style="margin-top:12px;padding:12px;background:rgba(79,172,254,0.06);border-radius:8px;font-size:12px">
                <div>每月节省利息: <strong style="color:var(--green)">¥{{ fmt(prepayModal.amount * prepayModal.rate / 12) }}</strong></div>
                <div>一年节省利息: <strong style="color:var(--green)">¥{{ fmt(prepayModal.amount * prepayModal.rate) }}</strong></div>
                <div>十年节省利息: <strong style="color:var(--green)">¥{{ fmt(prepayModal.amount * prepayModal.rate * 10) }}</strong></div>
                <div style="margin-top:8px;color:#888">剩余本金将降至: <strong style="color:var(--yellow)">¥{{ fmt(Math.max(0, prepayModal.principal - prepayModal.amount)) }}</strong></div>
            </div>
            <button class="btn btn-secondary" @click="prepayModal.show = false" style="margin-top:12px;width:100%">关闭</button>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], persons: [], showModal: false, editing: null, editPrincipal: 0, selectedIds: [], form: { person_id: 1, bank: '', house_name: '', total_amount: 0, remaining_principal: 0, rate: 0.04, start_date: todayStr(), end_date: null, total_periods: 360, monthly_payment: 0, repay_method: 'equal_installment' }, prepayModal: { show: false, bank: '', house: '', principal: 0, rate: 0, payment: 0, amount: 0 } };
    },
    async mounted() { await this.load(); },
    methods: {
        openPrepay(m) {
            this.prepayModal = { show: true, bank: m.bank, house: m.house_name, principal: m.remaining_principal, rate: m.rate, payment: m.monthly_payment, amount: 0 };
        },
        fmt,
        async load() {
            try { this.persons = await api('/persons/'); } catch(e) {}
            try { this.items = await api('/mortgages/'); } catch(e) {}
            if (this.persons.length) this.form.person_id = this.persons[0].id;
        },
        openCreate() {
            this.editing = null;
            this.form = { person_id: this.persons[0]?.id || 1, bank: '', house_name: '', total_amount: 0, remaining_principal: 0, rate: 0.04, start_date: todayStr(), end_date: null, total_periods: 360, monthly_payment: 0, repay_method: 'equal_installment' };
            this.showModal = true;
        },
        openEdit(m) { this.editing = m; this.editPrincipal = m.remaining_principal; this.showModal = true; },
        async create() {
            if (!this.form.bank || !this.form.total_amount) return this.showToast('请填写必填项', 'error');
            const body = { ...this.form };
            if (!body.end_date) delete body.end_date;
            try { await api('/mortgages/', { method: 'POST', body: JSON.stringify(body) }); this.showToast('房贷已添加'); this.showModal = false; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async updatePrincipal() {
            try { await api('/mortgages/' + this.editing.id + '?remaining_principal=' + this.editPrincipal, { method: 'PATCH' }); this.showToast('本金已更新'); this.showModal = false; this.editing = null; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/mortgages/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Incomes ----
const IncomesPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>收入管理</h2><p>记录每月/年度/一次性收入</p></div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增收入</button>
    <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/incomes/' + id, { method: 'DELETE' }))" style="margin-bottom:12px;margin-left:8px">批量删除</button>
    <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>人员</th><th>金额</th><th>来源</th><th>类型</th><th>周期</th><th>操作</th></tr></thead>
        <tbody><tr v-for="i in items" :key="i.id">
            <td><input type="checkbox" :checked="selectedIds.includes(i.id)" @change="toggleSelect(i.id)"></td>
            <td>{{ i.id }}</td><td>{{ i.person?.name || '-' }}</td><td style="color:var(--green)">¥{{ fmt(i.amount) }}</td><td>{{ i.source }}</td>
            <td><span class="tag blue">{{ periodTypeLabel(i.period_type) }}</span></td><td>{{ i.period_value }}</td>
            <td><button class="btn btn-secondary btn-xs" @click="openEdit(i)" style="margin-right:4px">编辑</button><button class="btn btn-danger btn-xs" @click="remove(i.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="items.length === 0" class="empty-state">暂无收入记录</div>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '编辑' : '新增' }}收入</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01" placeholder="0.00"></div>
            <div class="form-group"><label>来源</label><input v-model="form.source" list="source-list" placeholder="工资/兼职/投资/租金/其他"><datalist id="source-list"><option value="工资"><option value="兼职"><option value="投资"><option value="租金"><option value="理财"><option value="其他"></datalist></div>
            <div class="form-row">
                <div class="form-group"><label>类型</label><select v-model="form.period_type"><option value="monthly">月度</option><option value="yearly">年度</option><option value="once">一次性</option></select></div>
                <div class="form-group"><label>周期 (如 2025-05)</label><input v-model="form.period_value" :placeholder="todayStr().slice(0,7)"></div>
            </div>
            <div class="form-group"><label>备注</label><input v-model="form.note" placeholder="收入备注"></div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="submit">{{ editing ? '保存修改' : '确认' }}</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], persons: [], showModal: false, editing: null, selectedIds: [], form: { person_id: 1, amount: 0, source: '', period_type: 'monthly', period_value: todayStr().slice(0, 7), note: '' } };
    },
    async mounted() { await this.load(); },
    methods: {
        fmt, todayStr,
        async load() {
            try { this.persons = await api('/persons/'); } catch(e) {}
            try { this.items = await api('/incomes/'); } catch(e) {}
            if (this.persons.length) this.form.person_id = this.persons[0].id;
        },
        periodTypeLabel(t) { const m = { monthly: '月度', yearly: '年度', once: '一次性' }; return m[t] || t; },
        openCreate() { this.editing = null; this.form = { person_id: this.persons[0]?.id || 1, amount: 0, source: '', period_type: 'monthly', period_value: todayStr().slice(0, 7), note: '' }; this.showModal = true; },
        openEdit(i) { this.editing = i; this.form = { person_id: i.person_id, amount: i.amount, source: i.source || '', period_type: i.period_type || 'monthly', period_value: i.period_value || todayStr().slice(0, 7), note: i.note || '' }; this.showModal = true; },
        async submit() {
            if (!this.form.amount || !this.form.source) return this.showToast('请填写金额和来源', 'error');
            if (this.editing) {
                try { await api('/incomes/' + this.editing.id, { method: 'PATCH', body: JSON.stringify(this.form) }); this.showToast('收入已更新'); this.showModal = false; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            } else {
                try { await api('/incomes/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('收入已记录'); this.showModal = false; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
            }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/incomes/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Expenses ----
const ExpensesPage = {
    mixins: [ToastMixin, BatchDeleteMixin],
    template: `
<div>
    <div class="page-header"><h2>支出管理</h2><p>记录日常消费支出</p></div>
    <div class="filter-bar">
        <span class="filter-chip" :class="{ active: !filterCat }" @click="filterCat = null">全部</span>
        <span class="filter-chip" v-for="c in cats" :key="c" :class="{ active: filterCat === c }" @click="filterCat = c">{{ c }}</span>
    </div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增支出</button>
    <button class="btn btn-danger btn-sm" @click="batchDelete(id => api('/expenses/' + id, { method: 'DELETE' }))" style="margin-bottom:12px;margin-left:8px">批量删除</button>
    <table class="data-table"><thead><tr><th style="width:30px"><input type="checkbox" @change="toggleSelectAll"></th><th>ID</th><th>人员</th><th>金额</th><th>分类</th><th>周期</th><th>日期</th><th>备注</th><th>操作</th></tr></thead>
        <tbody><tr v-for="e in filteredExpenses" :key="e.id">
            <td><input type="checkbox" :checked="selectedIds.includes(e.id)" @change="toggleSelect(e.id)"></td>
            <td>{{ e.id }}</td><td>{{ e.person?.name || '-' }}</td><td style="color:var(--red)">¥{{ fmt(e.amount) }}</td>
            <td><span class="tag yellow">{{ e.category }}</span></td><td>{{ e.period_value }}</td><td>{{ e.expense_date }}</td>
            <td style="color:#888;font-size:11px">{{ e.note }}</td>
            <td><button class="btn btn-danger btn-xs" @click="remove(e.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="items.length === 0" class="empty-state">暂无支出记录</div>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>新增支出</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01" placeholder="0.00"></div>
            <div class="form-row">
                <div class="form-group"><label>分类</label><input v-model="form.category" list="cat-list" placeholder="选择或输入自定义分类"><datalist id="cat-list"><option v-for="c in cats" :key="c" :value="c"></datalist></div>
                <div class="form-group"><label>周期</label><input v-model="form.period_value" :placeholder="todayStr().slice(0,7)"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>日期</label><input v-model="form.expense_date" type="date"></div>
                <div class="form-group"><label>备注</label><input v-model="form.note" placeholder="消费说明"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="create">确认</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        const cats = ['餐饮', '交通', '购物', '娱乐', '医疗', '教育', '居住', '通讯', '日用', '其他'];
        return { items: [], persons: [], cats, filterCat: null, showModal: false, selectedIds: [], form: { person_id: 1, amount: 0, category: '餐饮', period_value: todayStr().slice(0, 7), expense_date: todayStr(), note: '' } };
    },
    async mounted() { await this.load(); },
    computed: {
        filteredExpenses() { return this.filterCat ? this.items.filter(e => e.category === this.filterCat) : this.items; }
    },
    methods: {
        fmt, todayStr,
        async load() {
            try { this.persons = await api('/persons/'); } catch(e) {}
            try { this.items = await api('/expenses/'); } catch(e) {}
            if (this.persons.length) this.form.person_id = this.persons[0].id;
        },
        openCreate() { this.form = { person_id: this.persons[0]?.id || 1, amount: 0, category: '餐饮', period_value: todayStr().slice(0, 7), expense_date: todayStr(), note: '' }; this.showModal = true; },
        async create() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            try { await api('/expenses/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('支出已记录'); this.showModal = false; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/expenses/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Transactions (Unified Log) ----
const TransactionsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>统一流水</h2><p>查看所有财务交易记录</p></div>
    <div class="filter-bar">
        <span class="filter-chip" :class="{ active: !filter.type }" @click="filter.type = null">全部</span>
        <span class="filter-chip" v-for="t in types" :key="t.value" :class="{ active: filter.type === t.value }" @click="filter.type = filter.type === t.value ? null : t.value">{{ t.label }}</span>
        <span style="flex:1"></span>
        <input type="date" v-model="filter.date_from" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px" title="开始日期">
        <span style="color:#888;font-size:11px">至</span>
        <input type="date" v-model="filter.date_to" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px" title="结束日期">
        <button class="btn btn-secondary btn-sm" @click="load">查询</button>
    </div>
    <table class="data-table"><thead><tr><th>ID</th><th>类型</th><th>金额</th><th>时间</th></tr></thead>
        <tbody><tr v-for="t in items" :key="t.type + t.id">
            <td>{{ t.id }}</td>
            <td><span :class="'tag ' + typeColor(t.type)">{{ typeLabel(t.type) }}</span></td>
            <td :style="{ color: t.type === 'expense' || t.type === 'card_trans' ? 'var(--red)' : 'var(--green)' }">¥{{ fmt(t.amount) }}</td>
            <td style="color:#888">{{ t.txn_date?.split('T')[0] || t.txn_date }}</td>
        </tr></tbody>
    </table>
    <div v-if="items.length === 0" class="empty-state">暂无流水记录</div>
    <div class="pagination" v-if="total > pageSize">
        <button class="btn btn-secondary btn-xs" :disabled="page <= 1" @click="page--; load()">上一页</button>
        <span style="color:#888">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
        <button class="btn btn-secondary btn-xs" :disabled="page >= Math.ceil(total / pageSize)" @click="page++; load()">下一页</button>
    </div>
</div>`,
    data() {
        return {
            items: [], total: 0, page: 1, pageSize: 20,
            types: [
                { label: '贷款', value: 'loan' }, { label: 'POS刷卡', value: 'pos' },
                { label: '分期', value: 'installment' }, { label: '信用卡消费', value: 'card_trans' },
                { label: '收入', value: 'income' }, { label: '支出', value: 'expense' }
            ],
            filter: { type: null, date_from: null, date_to: null }
        };
    },
    async mounted() { await this.load(); },
    methods: {
        fmt,
        typeLabel(t) {
            const m = { loan: '贷款', pos: 'POS刷卡', installment: '分期', card_trans: '信用卡消费', income: '收入', expense: '支出' };
            return m[t] || t;
        },
        typeColor(t) {
            const m = { loan: 'red', pos: 'blue', installment: 'yellow', card_trans: 'red', income: 'green', expense: 'red' };
            return m[t] || '';
        },
        async load() {
            let url = '/transactions/?page=' + this.page + '&page_size=' + this.pageSize;
            if (this.filter.type) url += '&type=' + this.filter.type;
            if (this.filter.date_from) url += '&date_from=' + this.filter.date_from;
            if (this.filter.date_to) url += '&date_to=' + this.filter.date_to;
            try {
                const data = await api(url);
                this.items = data.items || [];
                this.total = data.total || 0;
            } catch(e) { this.showToast(e.message, 'error'); }
        }
    }
};

// ---- Reports ----
const ReportsPage = {
    mixins: [ToastMixin, ChartMixin],
    template: `
<div>
    <div class="page-header"><h2>统计报告</h2><p>多维度财务数据分析</p></div>

    <!-- 债务汇总 -->
    <div class="section-title" style="cursor:pointer" @click="showDebtSummary = !showDebtSummary">债务汇总（按平台/银行） <span style="font-size:10px;color:#888">{{ showDebtSummary ? '收起' : '展开' }}</span></div>
    <div v-if="showDebtSummary && debtSummary">
        <div class="section-title" style="font-size:12px;color:var(--red)">借贷待还</div>
        <table class="data-table"><thead><tr><th>平台</th><th>笔数</th><th>原始总额</th><th>待还本金</th><th>待还利息</th></tr></thead>
            <tbody><tr v-for="r in debtSummary.loan" :key="r.platform">
                <td>{{ r.platform }}</td><td>{{ r.count }}</td><td>¥{{ fmt(r.total_amount) }}</td>
                <td style="color:var(--red)">¥{{ fmt(r.pending_principal) }}</td><td style="color:var(--yellow)">¥{{ fmt(r.pending_interest) }}</td>
            </tr>
            <tr style="font-weight:bold;background:rgba(255,255,255,0.03)">
                <td>合计</td><td>{{ debtSummary.loan.reduce((s,r)=>s+r.count,0) }}</td>
                <td>¥{{ fmt(debtSummary.loan.reduce((s,r)=>s+r.total_amount,0)) }}</td>
                <td style="color:var(--red)">¥{{ fmt(debtSummaryLoanTotal) }}</td>
                <td style="color:var(--yellow)">¥{{ fmt(debtSummary.loan.reduce((s,r)=>s+r.pending_interest,0)) }}</td>
            </tr></tbody>
        </table>
        <div class="section-title" style="font-size:12px;color:var(--yellow)">分期剩余</div>
        <table class="data-table"><thead><tr><th>银行</th><th>笔数</th><th>原始总额</th><th>剩余本金</th></tr></thead>
            <tbody><tr v-for="r in debtSummary.installment" :key="r.bank">
                <td>{{ r.bank }}</td><td>{{ r.count }}</td><td>¥{{ fmt(r.total_amount) }}</td><td style="color:var(--yellow)">¥{{ fmt(r.remaining) }}</td>
            </tr></tbody>
        </table>
        <div class="section-title" style="font-size:12px;color:var(--blue)">信用卡未还账单</div>
        <table class="data-table"><thead><tr><th>银行</th><th>笔数</th><th>账单总额</th><th>已还</th><th>未还</th></tr></thead>
            <tbody><tr v-for="r in debtSummary.bill" :key="r.bank">
                <td>{{ r.bank }}</td><td>{{ r.count }}</td><td>¥{{ fmt(r.bill_amount) }}</td><td style="color:var(--green)">¥{{ fmt(r.paid_amount) }}</td><td style="color:var(--red)">¥{{ fmt(r.unpaid) }}</td>
            </tr></tbody>
        </table>
        <div style="margin-top:12px;font-size:12px;color:var(--red);text-align:right">
            不含房贷总负债: ¥{{ fmt(debtSummaryLoanTotal + debtSummaryInstTotal + debtSummaryBillTotal) }}
        </div>
    </div>

    <!-- 利息统计 -->
    <div class="section-title">利息/手续费统计</div>
    <div class="filter-bar" style="margin-bottom:12px">
        <span class="filter-chip" :class="{ active: interestStatType === 'yearly' }" @click="switchInterestType('yearly')">按年</span>
        <span class="filter-chip" :class="{ active: interestStatType === 'monthly' }" @click="switchInterestType('monthly')">按月</span>
        <span class="filter-chip" :class="{ active: interestStatType === 'range' }" @click="switchInterestType('range')">区间</span>
        <template v-if="interestStatType === 'monthly'">
            <input v-model="interestMonth" type="month" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:150px">
        </template>
        <template v-if="interestStatType === 'yearly'">
            <input v-model.number="interestYear" type="number" min="2020" max="2100" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:80px" placeholder="年份">
        </template>
        <template v-if="interestStatType === 'range'">
            <input v-model="interestFrom" type="date" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px">
            <span style="color:#888;font-size:11px">至</span>
            <input v-model="interestTo" type="date" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px">
        </template>
        <button class="btn btn-secondary btn-sm" @click="loadInterestStats">查询</button>
    </div>
    <div class="stat-cards" style="margin-bottom:16px;grid-template-columns:repeat(5,1fr)">
        <div class="stat-card" style="cursor:pointer" @click="showInterestDetail('总利息/手续费', 'total')"><div class="label">总利息/手续费</div><div class="value yellow">{{ fmt(interestStats.total_interest) }}</div></div>
        <div class="stat-card" style="cursor:pointer" @click="showInterestDetail('贷款已付利息', 'loan_interest')"><div class="label">贷款已付利息</div><div class="value red">{{ fmt(interestStats.loan_interest) }}</div></div>
        <div class="stat-card" style="cursor:pointer" @click="showInterestDetail('POS手续费', 'pos_fee')"><div class="label">POS手续费</div><div class="value blue">{{ fmt(interestStats.pos_fee) }}</div></div>
        <div class="stat-card" style="cursor:pointer" @click="showInterestDetail('分期手续费', 'installment_fee')"><div class="label">分期手续费</div><div class="value yellow">{{ fmt(interestStats.installment_fee) }}</div></div>
        <div class="stat-card" style="cursor:pointer" @click="showInterestDetail('房贷利息', 'mortgage_interest')"><div class="label">房贷月利息（近似）</div><div class="value green">{{ fmt(interestStats.mortgage_interest || 0) }}</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-box"><div class="title">利息/手续费构成</div><div ref="interestPieChart" class="chart-inner"></div></div>
        <div class="chart-box"><div class="title">各平台贷款分布</div><div ref="platformChart" class="chart-inner"></div></div>
    </div>

    <!-- 收支缺口 -->
    <div class="section-title">收支缺口分析</div>
    <div class="filter-bar" style="margin-bottom:12px">
        <input v-model="gapMonthInput" type="month" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:160px" @change="loadGap">
        <button class="btn btn-secondary btn-sm" @click="loadGap">分析</button>
    </div>
    <div v-if="gap" :class="'gap-box ' + (gap.gap < 0 ? 'negative' : 'positive')">
        <div style="font-size:12px;color:#888;margin-bottom:4px">{{ gap.period }} 收支分析</div>
        <div :style="{ fontSize: '28px', fontWeight: 'bold', color: gap.gap < 0 ? 'var(--red)' : 'var(--green)' }">¥{{ fmt(Math.abs(gap.gap)) }}</div>
        <div style="font-size:13px;color:#888;margin-top:4px">{{ gap.gap < 0 ? '入不敷出' : '收支有盈余' }}</div>
        <div style="display:flex;justify-content:center;gap:24px;margin-top:12px;font-size:12px;color:#888">
            <div>收入: <span style="color:var(--green)">¥{{ fmt(gap.total_income) }}</span></div>
            <div>日常支出: <span style="color:var(--red)">¥{{ fmt(gap.daily_expense) }}</span></div>
            <div>待还款: <span style="color:var(--yellow)">¥{{ fmt(gap.debt_payment) }}</span></div>
        </div>
    </div>

    <div v-if="gapDetail" style="margin-top:16px;padding:20px;background:linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.06));border:1px solid rgba(59,130,246,0.25);border-radius:10px;text-align:left;font-size:12px;line-height:1.8">
        <div style="color:var(--blue);font-weight:bold;font-size:14px;margin-bottom:8px">分析总结与改进方案</div>

        <div style="color:var(--blue);font-weight:bold;margin-bottom:6px">数据洞察</div>
        <div v-for="(obs, idx) in gapDetail.observations" :key="idx" style="margin-bottom:6px;display:flex;align-items:flex-start;gap:6px">
            <span :style="{ color: obs.severity === 'critical' ? 'var(--red)' : obs.severity === 'warning' ? 'var(--yellow)' : obs.severity === 'positive' ? 'var(--green)' : '#888' }">
                {{ obs.severity === 'critical' ? '●' : obs.severity === 'warning' ? '◆' : obs.severity === 'positive' ? '▲' : '○' }}
            </span>
            <span style="color:#ccc">{{ obs.text }}</span>
        </div>
        <div v-if="!gapDetail.observations || gapDetail.observations.length === 0" style="color:#666">暂无特别洞察，财务状况平稳</div>

        <div style="color:var(--yellow);font-weight:bold;margin-top:12px;margin-bottom:6px">改进建议</div>
        <div v-for="(rec, idx) in gapDetail.recommendations" :key="idx" style="margin-bottom:8px">
            <div style="display:flex;align-items:flex-start;gap:4px">
                <span :style="{ color: rec.impact === 'high' ? 'var(--red)' : rec.impact === 'medium' ? 'var(--yellow)' : '#888', fontWeight: 'bold' }">{{ idx + 1 }}.</span>
                <span style="color:#ccc">{{ rec.text }}</span>
            </div>
            <div v-if="rec.action" style="color:#888;margin-left:18px;font-size:11px;margin-top:2px">{{ rec.action }}</div>
        </div>
        <div v-if="!gapDetail.recommendations || gapDetail.recommendations.length === 0" style="color:#666">暂无特别建议，保持当前良好习惯</div>

        <div v-if="gapDetail.benchmarks" style="color:#666;font-size:10px;margin-top:12px;border-top:1px solid rgba(255,255,255,0.08);padding-top:8px">
            <div>参考基准：通胀率 {{ gapDetail.benchmarks.china_inflation_rate }} · 建议储蓄率 {{ gapDetail.benchmarks.recommended_savings_rate }} · 健康负债率 {{ gapDetail.benchmarks.healthy_debt_to_income }}</div>
            <div>数据来源：{{ gapDetail.benchmarks.source }}</div>
        </div>
    </div>
    <div v-else style="margin-top:16px;padding:20px;background:linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.06));border:1px solid rgba(59,130,246,0.25);border-radius:10px;text-align:center;font-size:12px;color:#666">
        请选择时间范围并点击「分析」按钮，查看收支分析总结与改进建议
    </div>

    <!-- 支出分类 -->
    <div class="section-title" v-if="gap && gap.expense_breakdown">支出分类明细</div>
    <div class="chart-row" v-if="gap && gap.expense_breakdown">
        <div class="chart-box" style="grid-column:1 / -1"><div class="title">支出分类占比</div><div ref="expensePieChart" class="chart-inner"></div></div>
    </div>

    <!-- 月度POS手续费（原有） -->
    <div class="chart-row">
        <div class="chart-box" style="grid-column:1 / -1"><div class="title">月度POS手续费趋势</div><div ref="monthChart" class="chart-inner" style="height:280px"></div></div>
    </div>

    <!-- POS刷卡次数统计 -->
    <div class="section-title">POS刷卡次数统计</div>
    <div class="filter-bar" style="margin-bottom:12px">
        <span class="filter-chip" :class="{ active: posCountType === 'yearly' }" @click="switchPosCountType('yearly')">按年</span>
        <span class="filter-chip" :class="{ active: posCountType === 'monthly' }" @click="switchPosCountType('monthly')">按月</span>
        <span class="filter-chip" :class="{ active: posCountType === 'range' }" @click="switchPosCountType('range')">区间</span>
        <template v-if="posCountType === 'monthly'">
            <input v-model="posCountMonth" type="month" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:150px">
        </template>
        <template v-if="posCountType === 'yearly'">
            <input v-model.number="posCountYear" type="number" min="2020" max="2100" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:80px" placeholder="年份">
        </template>
        <template v-if="posCountType === 'range'">
            <input v-model="posCountFrom" type="date" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px">
            <span style="color:#888;font-size:11px">至</span>
            <input v-model="posCountTo" type="date" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px">
        </template>
        <button class="btn btn-secondary btn-sm" @click="loadPosCount">查询</button>
    </div>
    <div class="stat-cards" style="margin-bottom:16px;grid-template-columns:repeat(3,1fr)">
        <div class="stat-card"><div class="label">总刷卡次数</div><div class="value blue">{{ posCountData.total_count || 0 }}</div></div>
        <div class="stat-card"><div class="label">统计周期</div><div class="value" style="font-size:14px">{{ posCountData.period }}</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-box" style="grid-column:1 / -1"><div class="title">POS刷卡次数趋势</div><div ref="posCountChart" class="chart-inner" style="height:280px"></div></div>
    </div>

    <!-- 支出分类占比 -->
    <div class="section-title">支出分类分析</div>
    <div class="chart-row">
        <div class="chart-box" style="grid-column:1 / -1"><div class="title">本月支出分类占比</div><div ref="expenseCatChart" class="chart-inner" style="height:280px"></div></div>
    </div>

    <!-- 优先还款方案 -->
    <div class="section-title" style="display:flex;align-items:center;gap:8px">
        优先还款方案
        <span class="filter-chip" :class="{ active: priorityMethod === 'avalanche' }" @click="switchPriorityMethod('avalanche')">雪崩法</span>
        <span class="filter-chip" :class="{ active: priorityMethod === 'snowball' }" @click="switchPriorityMethod('snowball')">雪球法</span>
    </div>
    <div v-if="priorityPlan.items && priorityPlan.items.length" style="margin-bottom:20px">
        <div style="font-size:12px;color:#888;margin-bottom:8px">{{ priorityPlan.method }} · 总债务 ¥{{ fmt(priorityPlan.total_debt) }} · 月利息约 ¥{{ fmt(priorityPlan.total_monthly_interest) }}</div>
        <table class="data-table"><thead><tr><th>优先级</th><th>类型</th><th>名称</th><th>人员</th><th>余额</th><th>年化利率</th><th>备注</th></tr></thead>
            <tbody><tr v-for="(item, idx) in priorityPlan.items" :key="idx" :style="{ background: idx === 0 ? 'rgba(233,69,96,0.08)' : '' }">
                <td><span :class="'badge ' + (idx === 0 ? 'red' : idx <= 2 ? 'yellow' : 'blue')">#{{ idx + 1 }}</span></td>
                <td><span :class="'tag ' + (item.debt_type === '信用卡' ? 'red' : item.debt_type === '分期' ? 'yellow' : item.debt_type === '贷款' ? 'blue' : 'green')">{{ item.debt_type }}</span></td>
                <td>{{ item.name }}</td><td>{{ item.person_name }}</td>
                <td :style="{ color: 'var(--red)' }">¥{{ fmt(item.balance) }}</td>
                <td><span :style="{ color: idx === 0 ? 'var(--red)' : '' }">{{ item.rate_label }}</span></td>
                <td style="color:#888;font-size:11px">{{ item.note }}</td>
            </tr></tbody>
        </table>
        <div v-if="priorityPlan.comparison" style="margin-top:12px">
            <div style="font-size:12px;color:var(--blue);margin-bottom:6px">📊 两种方案对比（预估月还款 ¥{{ fmt(priorityPlan.total_monthly_interest + priorityPlan.total_debt * 0.02) }}）</div>
            <table class="data-table"><thead><tr><th></th><th>雪崩法</th><th>雪球法</th></tr></thead>
                <tbody><tr>
                    <td>预计还清</td>
                    <td :style="{ color: 'var(--yellow)' }">{{ priorityPlan.comparison.avalanche.months }} 个月</td>
                    <td :style="{ color: 'var(--blue)' }">{{ priorityPlan.comparison.snowball.months }} 个月</td>
                </tr><tr>
                    <td>总利息</td>
                    <td style="color:var(--green)">¥{{ fmt(priorityPlan.comparison.avalanche.total_interest) }}</td>
                    <td>¥{{ fmt(priorityPlan.comparison.snowball.total_interest) }}</td>
                </tr><tr>
                    <td>特点</td><td style="font-size:11px;color:#888">{{ priorityPlan.comparison.avalanche.description }}</td>
                    <td style="font-size:11px;color:#888">{{ priorityPlan.comparison.snowball.description }}</td>
                </tr></tbody>
            </table>
        </div>
    </div>

    <!-- 负债趋势预测 -->
    <div class="section-title">负债趋势预测</div>
    <div class="filter-bar" style="margin-bottom:12px">
        <span class="filter-chip" :class="{ active: forecastMonths === 3 }" @click="switchForecast(3)">3个月</span>
        <span class="filter-chip" :class="{ active: forecastMonths === 6 }" @click="switchForecast(6)">6个月</span>
        <span class="filter-chip" :class="{ active: forecastMonths === 12 }" @click="switchForecast(12)">12个月</span>
        <span class="filter-chip" :class="{ active: forecastMonths === 'nextYear' }" @click="switchForecast('nextYear')">明年</span>
        <label style="margin-left:12px;font-size:11px;color:#888;display:flex;align-items:center;gap:4px;cursor:pointer">
            <input type="checkbox" v-model="forecastIncludeMtg" @change="loadForecast" style="accent-color:var(--red);cursor:pointer">
            含房贷
        </label>
    </div>
    <div class="filter-bar" style="margin-bottom:12px">
        <span style="font-size:11px;color:#888">月结余:</span>
        <input v-model.number="forecastSurplus" type="number" step="100" style="padding:3px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:100px" @change="loadForecast" placeholder="自动计算">
        <span style="font-size:11px;color:#666">（自动: ¥{{ fmt(forecastData.trends?.auto_monthly_surplus || 0) }}，正值=结余还债，负值=缺口）</span>
        <span style="font-size:11px;color:#888;margin-left:8px">月新增借款:</span>
        <input v-model.number="forecastNewBorrowing" type="number" step="100" min="0" style="padding:3px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:100px" @change="loadForecast" placeholder="0">
    </div>
    <div v-if="forecastData.trend_desc" style="font-size:12px;color:#e94560;margin-bottom:12px;padding:8px;background:rgba(233,69,96,0.06);border-radius:6px">{{ forecastData.trend_desc }}</div>
    <div class="chart-row" v-if="forecastData.forecasts && forecastData.forecasts.length">
        <div class="chart-box" style="grid-column:1 / -1"><div class="title">负债推演</div><div ref="forecastChart" class="chart-inner" style="height:320px"></div></div>
    </div>

    <!-- 利息明细弹窗 -->
    <div v-if="interestDetailModal.show" class="modal-overlay" @click.self="interestDetailModal.show = false">
        <div class="modal" style="width:650px;max-height:75vh">
            <h3>{{ interestDetailModal.title }}</h3>
            <div style="overflow-y:auto;max-height:55vh">
                <table class="data-table"><thead><tr>
                    <th v-if="interestDetailModal.isMultiMonth" style="width:70px">月份</th>
                    <th v-if="interestDetailModal.detailType === 'total'" style="width:80px">类型</th>
                    <th>项目</th><th>人员</th><th>金额</th><th>备注</th>
                </tr></thead>
                    <tbody><tr v-for="(item, idx) in interestDetailModal.items" :key="idx">
                        <td v-if="interestDetailModal.isMultiMonth" style="font-size:10px;color:#888">{{ item.period }}</td>
                        <td v-if="interestDetailModal.detailType === 'total'">
                            <span :class="'tag ' + (item._type === 'loan_interest' ? 'red' : item._type === 'pos_fee' ? 'blue' : item._type === 'installment_fee' ? 'yellow' : 'green')">{{ intTypeLabel(item._type) }}</span>
                        </td>
                        <td>{{ item.name }}</td><td>{{ item.person || '' }}</td>
                        <td :style="{ color: 'var(--yellow)' }">¥{{ fmt(item.amount) }}</td>
                        <td style="font-size:10px;color:#888">{{ item.note || '' }}</td>
                    </tr></tbody>
                </table>
            </div>
            <div style="margin-top:12px;text-align:right;font-size:12px;color:var(--yellow)">
                合计: ¥{{ fmt(interestDetailModal.items.reduce((s,i) => s + (i.amount || 0), 0)) }}
            </div>
            <button class="btn btn-secondary" @click="interestDetailModal.show = false" style="margin-top:8px;width:100%">关闭</button>
        </div>
    </div>
</div>`,
    data() {
        const now = new Date();
        return {
            summary: { total_active_loans: 0, total_pos_fees: 0 },
            platformData: [], monthData: [],
            gap: null,
            gapMonthInput: now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0'),
            // interest stats
            interestStatType: 'yearly',
            interestYear: now.getFullYear(),
            interestMonth: now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0'),
            interestFrom: '',
            interestTo: '',
            interestStats: { total_interest: 0, loan_interest: 0, pos_fee: 0, installment_fee: 0, mortgage_interest: 0 },
            interestDetailModal: { show: false, title: '', items: [], isMultiMonth: false },
            priorityPlan: { items: [], total_debt: 0, total_monthly_interest: 0, method: '' },
            forecastData: { forecasts: [], trend_desc: '', base: {}, trends: {} },
            forecastMonths: 12,
            forecastIncludeMtg: false,
            forecastSurplus: null,
            forecastNewBorrowing: 0,
            gapDetail: null,
            priorityMethod: 'avalanche',
            // POS刷卡次数统计
            posCountType: 'yearly',
            posCountYear: new Date().getFullYear(),
            posCountMonth: new Date().getFullYear() + '-' + String(new Date().getMonth() + 1).padStart(2, '0'),
            posCountFrom: '',
            posCountTo: '',
            posCountData: { period: '', total_count: 0, items: [] },
            showDebtSummary: false,
            debtSummary: null,
        };
    },
    computed: {
        debtSummaryLoanTotal() { return this.debtSummary ? this.debtSummary.loan.reduce((s,r) => s + r.pending_principal, 0) : 0; },
        debtSummaryInstTotal() { return this.debtSummary ? this.debtSummary.installment.reduce((s,r) => s + r.remaining, 0) : 0; },
        debtSummaryBillTotal() { return this.debtSummary ? this.debtSummary.bill.reduce((s,r) => s + r.unpaid, 0) : 0; },
    },
    async mounted() {
        try { this.summary = await api('/reports/summary'); } catch(e) {}
        try { this.platformData = await api('/reports/by-platform'); } catch(e) {}
        try { this.monthData = await api('/reports/by-month'); } catch(e) {}
        await this.loadGap();
        await this.loadInterestStats();
        await this.loadPriorityPlan();
        await this.loadForecast();
        await this.loadPosCount();
        try { this.debtSummary = await api('/reports/debt-summary'); } catch(e) {}
        this.$nextTick(() => { this.renderPlatform(); this.renderMonth(); this.renderForecast(); this.renderExpenseCat(); });
    },
    methods: {
        fmt,
        // Y轴单位动态格式化
        axisUnit(v) {
            const abs = Math.abs(v);
            if (abs >= 10000) return '¥' + (v / 10000).toFixed(1) + '万';
            if (abs >= 1000) return '¥' + (v / 1000).toFixed(1) + '千';
            return '¥' + v;
        },
        // 负债趋势Y轴格式化（大额用万）
        axisUnitWan(v) {
            if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + '万';
            return '¥' + v;
        },
        switchInterestType(type) {
            this.interestStatType = type;
            this.loadInterestStats();
        },
        intTypeLabel(t) { const m = { loan_interest: '贷款利息', pos_fee: 'POS手续费', installment_fee: '分期手续费', mortgage_interest: '房贷利息' }; return m[t] || t; },
        async showInterestDetail(title, type) {
            let url = '/reports/interest-detail?stat_type=' + this.interestStatType;
            if (this.interestStatType === 'yearly') url += '&year=' + this.interestYear;
            else if (this.interestStatType === 'monthly') { const [y, m] = this.interestMonth.split('-'); url += '&year=' + y + '&month=' + parseInt(m); }
            else if (this.interestStatType === 'range' && this.interestFrom && this.interestTo) url += '&date_from=' + this.interestFrom + '&date_to=' + this.interestTo;
            try {
                const data = await api(url);
                let items = [];
                if (type === 'total') {
                    // 总利息 = 合并所有类型
                    for (const t of ['loan_interest', 'pos_fee', 'installment_fee', 'mortgage_interest']) {
                        const arr = data[t] || [];
                        items = items.concat(arr.map(i => ({ ...i, _type: t })));
                    }
                } else {
                    items = data[type] || [];
                }
                this.interestDetailModal = { show: true, title: title, items: items, isMultiMonth: data.is_multi_month, detailType: type };
            } catch(e) { this.showToast(e.message, 'error'); }
        },
        async loadInterestStats() {
            let url = '/reports/interest-stats?stat_type=' + this.interestStatType;
            if (this.interestStatType === 'yearly') {
                url += '&year=' + this.interestYear;
            } else if (this.interestStatType === 'monthly') {
                const [y, m] = this.interestMonth.split('-');
                url += '&year=' + y + '&month=' + parseInt(m);
            } else if (this.interestStatType === 'range') {
                if (this.interestFrom && this.interestTo) {
                    url += '&date_from=' + this.interestFrom + '&date_to=' + this.interestTo;
                }
            }
            try { this.interestStats = await api(url); } catch(e) {}
            this.$nextTick(() => this.renderInterestPie());
        },
        async loadGap() {
            const [y, m] = this.gapMonthInput ? this.gapMonthInput.split('-') : [new Date().getFullYear(), new Date().getMonth() + 1];
            try {
                this.gap = await api('/reports/gap-analysis?year=' + y + '&month=' + parseInt(m));
                this.gapDetail = await api('/reports/gap-analysis-detail?year=' + y + '&month=' + parseInt(m));
            } catch(e) {}
            this.$nextTick(() => {
                if (this.gap && this.gap.expense_breakdown) this.renderExpensePie();
            });
        },
        renderInterestPie() {
            const el = this.$refs.interestPieChart; if (!el) return;
            const chart = this._initChart(el);
            const data = [
                { value: this.interestStats.loan_interest || 0, name: '贷款利息' },
                { value: this.interestStats.pos_fee || 0, name: 'POS手续费' },
                { value: this.interestStats.installment_fee || 0, name: '分期手续费' },
                { value: this.interestStats.mortgage_interest || 0, name: '房贷利息' },
            ].filter(d => d.value > 0);
            if (data.length === 0) { chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } }); return; }
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: ¥{c}' },
                color: ['#e94560', '#4facfe', '#f9ca24', '#00d2a0'],
                series: [{
                    type: 'pie', radius: ['45%', '75%'], center: ['50%', '55%'],
                    data, label: { color: '#888', fontSize: 11 },
                    emphasis: { label: { fontSize: 16, fontWeight: 'bold' } }
                }]
            });

        },
        renderExpensePie() {
            const el = this.$refs.expensePieChart; if (!el) return;
            const chart = echarts.init(el);
            if (!this.gap || !this.gap.expense_breakdown || this.gap.expense_breakdown.length === 0) {
                chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } });
                return;
            }
            const colors = ['#e94560', '#4facfe', '#f9ca24', '#00d2a0', '#ff6b6b', '#a29bfe', '#fd79a8', '#fdcb6e', '#00cec9', '#6c5ce7'];
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: ¥{c}' },
                series: [{
                    type: 'pie', radius: '65%', center: ['50%', '55%'],
                    data: this.gap.expense_breakdown.map((d, i) => ({ value: d.amount, name: d.category, itemStyle: { color: colors[i % colors.length] } })),
                    label: { color: '#888', fontSize: 11 }
                }]
            });
            window.addEventListener('resize', () => chart.resize());
        },
        renderPlatform() {
            const el = this.$refs.platformChart; if (!el) return;
            const chart = echarts.init(el);
            if (this.platformData.length === 0) { chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } }); return; }
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: ¥{c}' },
                series: [{
                    type: 'pie', radius: '65%', center: ['50%', '55%'],
                    data: this.platformData.map(p => ({ value: p.total_amount, name: p.platform })),
                    label: { color: '#888', fontSize: 11 }
                }]
            });
            window.addEventListener('resize', () => chart.resize());
        },
        renderMonth() {
            const el = this.$refs.monthChart; if (!el) return;
            const chart = echarts.init(el);
            if (this.monthData.length === 0) { chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } }); return; }
            const maxVal = Math.max(...this.monthData.map(d => d.pos_fee));
            chart.setOption({
                tooltip: { trigger: 'axis' },
                grid: { left: 65, right: 20, top: 20, bottom: 30 },
                xAxis: { type: 'category', data: this.monthData.map(d => d.month), axisLabel: { color: '#888', fontSize: 10 } },
                yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => this.axisUnit(v) }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                series: [{ type: 'bar', data: this.monthData.map(d => d.pos_fee), itemStyle: { color: '#4facfe', borderRadius: [4,4,0,0] } }]
            });
            window.addEventListener('resize', () => chart.resize());
        },
        async loadPriorityPlan() {
            try { this.priorityPlan = await api('/reports/repay-priority?method=' + this.priorityMethod); } catch(e) {}
        },
        async switchPriorityMethod(m) {
            this.priorityMethod = m;
            await this.loadPriorityPlan();
        },
        async loadForecast() {
            let months = this.forecastMonths;
            if (months === 'nextYear') {
                const now = new Date();
                const monthsToNextJan = 13 - (now.getMonth() + 1);
                months = monthsToNextJan + 12;
            }
            let url = '/reports/debt-forecast?months=' + months + '&include_mortgage=' + this.forecastIncludeMtg;
            if (this.forecastSurplus !== null && this.forecastSurplus !== '') {
                url += '&monthly_surplus=' + this.forecastSurplus;
            }
            if (this.forecastNewBorrowing > 0) {
                url += '&monthly_new_borrowing=' + this.forecastNewBorrowing;
            }
            try {
                this.forecastData = await api(url);
            } catch(e) {}
            this.$nextTick(() => this.renderForecast());
        },
        switchForecast(val) {
            this.forecastMonths = val;
            this.loadForecast();
        },
        renderForecast() {
            const el = this.$refs.forecastChart; if (!el) return;
            let data = this.forecastData.forecasts || [];
            if (data.length === 0) { return; }
            if (this.forecastMonths === 'nextYear') {
                const nextYear = new Date().getFullYear() + 1;
                data = data.filter(d => d.month.startsWith(String(nextYear)));
            }
            const chart = echarts.init(el);
            const months = data.map(d => d.month);
            const now = new Date();
            const curLabel = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
            const legendData = this.forecastIncludeMtg
                ? ['总负债','贷款','信用卡','分期','房贷']
                : ['总负债','贷款','信用卡','分期'];
            const series = [
                { name: '总负债', type: 'line', data: data.map(d => this.forecastIncludeMtg ? d.total_debt : d.total_debt_ex_mortgage), lineStyle: { color: '#e94560', width: 2 }, itemStyle: { color: '#e94560' }, symbol: 'circle', symbolSize: 6 },
                { name: '贷款', type: 'line', data: data.map(d => d.loan_debt), lineStyle: { color: '#f9ca24', width: 1, type: 'dashed' }, itemStyle: { color: '#f9ca24' }, symbol: 'diamond', symbolSize: 4 },
                { name: '信用卡', type: 'line', data: data.map(d => d.card_debt), lineStyle: { color: '#4facfe', width: 1, type: 'dashed' }, itemStyle: { color: '#4facfe' }, symbol: 'triangle', symbolSize: 4 },
                { name: '分期', type: 'line', data: data.map(d => d.installment_debt), lineStyle: { color: '#ff6b6b', width: 1, type: 'dashed' }, itemStyle: { color: '#ff6b6b' }, symbol: 'rect', symbolSize: 4 },
            ];
            if (this.forecastIncludeMtg) {
                series.push({ name: '房贷', type: 'line', data: data.map(d => d.mortgage_debt), lineStyle: { color: '#00d2a0', width: 1, type: 'dashed' }, itemStyle: { color: '#00d2a0' }, symbol: 'roundRect', symbolSize: 4 });
            }
            chart.setOption({
                tooltip: { trigger: 'axis', formatter: function(params) {
                    let s = '<b>' + params[0].axisValue + '</b><br/>';
                    params.forEach(p => { s += p.marker + ' ' + p.seriesName + ': ¥' + p.value.toLocaleString() + '<br/>'; });
                    // 显示当月信用卡利息
                    const d = data[params[0].dataIndex];
                    if (d && d.card_interest_month > 0) {
                        s += '<span style="color:#e94560;font-size:10px">月利息 ¥' + d.card_interest_month.toLocaleString() + '</span>';
                    }
                    return s;
                }},
                legend: { data: legendData, textStyle: { color: '#888', fontSize: 11 }, top: 0 },
                grid: { left: 70, right: 20, top: 40, bottom: 30 },
                xAxis: { type: 'category', data: months, axisLabel: { color: '#888', fontSize: 10, rotate: 45 },
                    axisLine: { lineStyle: { color: '#666', type: 'dashed' } },
                },
                yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => (v / 10000).toFixed(0) + '万' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                series,
            });
            window.addEventListener('resize', () => chart.resize());
        },
        switchPosCountType(type) {
            this.posCountType = type;
            this.loadPosCount();
        },
        async loadPosCount() {
            let url = '/reports/pos-count?stat_type=' + this.posCountType;
            if (this.posCountType === 'yearly') {
                url += '&year=' + this.posCountYear;
            } else if (this.posCountType === 'monthly') {
                const [y, m] = this.posCountMonth.split('-');
                url += '&year=' + y + '&month=' + parseInt(m);
            } else if (this.posCountType === 'range') {
                if (this.posCountFrom && this.posCountTo) {
                    url += '&date_from=' + this.posCountFrom + '&date_to=' + this.posCountTo;
                }
            }
            try { this.posCountData = await api(url); } catch(e) {}
            this.$nextTick(() => this.renderPosCount());
        },
        renderPosCount() {
            const el = this.$refs.posCountChart; if (!el) return;
            const chart = echarts.init(el);
            const data = this.posCountData.items || [];
            if (data.length === 0) {
                chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } });
                return;
            }
            const maxVal = Math.max(...data.map(d => d.count));
            chart.setOption({
                tooltip: { trigger: 'axis', formatter: p => p[0].name + '<br/>刷卡次数: <b>' + p[0].value + '</b> 次' },
                grid: { left: 50, right: 20, top: 20, bottom: 30 },
                xAxis: {
                    type: 'category',
                    data: data.map(d => d.period),
                    axisLabel: { color: '#888', fontSize: 10, rotate: this.posCountType === 'yearly' ? 0 : 30 },
                },
                yAxis: {
                    type: 'value',
                    name: '次数',
                    minInterval: 1,
                    axisLabel: { color: '#888', fontSize: 10 },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                },
                series: [{
                    type: 'bar',
                    data: data.map(d => d.count),
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#4facfe' },
                            { offset: 1, color: 'rgba(79,172,254,0.2)' },
                        ]),
                        borderRadius: [4, 4, 0, 0],
                    },
                    barWidth: this.posCountType === 'monthly' ? '60%' : '40%',
                }],
            });
            window.addEventListener('resize', () => chart.resize());
        },
        renderExpenseCat() {
            const el = this.$refs.expenseCatChart; if (!el) return;
            const chart = echarts.init(el);
            if (!this.gap || !this.gap.expense_breakdown || !this.gap.expense_breakdown.length) {
                chart.setOption({ title: { text: '暂无数据（请先分析收支缺口）', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } });
                return;
            }
            const data = this.gap.expense_breakdown;
            const colors = ['#e94560', '#4facfe', '#f9ca24', '#00d2a0', '#ff6b6b', '#a29bfe', '#fd79a8', '#fdcb6e', '#00cec9', '#6c5ce7'];
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
                series: [{
                    type: 'pie', radius: ['40%', '70%'], center: ['50%', '55%'],
                    data: data.map((d, i) => ({ value: d.amount, name: d.category, itemStyle: { color: colors[i % colors.length] } })),
                    label: { color: '#888', fontSize: 11, formatter: '{b}\n{d}%' },
                    emphasis: { label: { fontSize: 14, fontWeight: 'bold' } }
                }]
            });
            window.addEventListener('resize', () => chart.resize());
        }
    }
};

// ---- Recycle Bin ----
const RecycleBinPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>回收站</h2><p>已删除的记录，支持恢复或永久删除</p></div>
    <button v-if="items.length > 0" class="btn btn-danger btn-sm" @click="clearAll" style="margin-bottom:12px">清空回收站</button>
    <table v-if="items.length > 0" class="data-table"><thead><tr><th>ID</th><th>数据表</th><th>原记录ID</th><th>数据预览</th><th>删除时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="r in items" :key="r.id">
            <td>{{ r.id }}</td>
            <td><span class="tag blue">{{ r.table_name }}</span></td>
            <td>{{ r.record_id }}</td>
            <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:#888">{{ r.preview }}</td>
            <td style="font-size:11px">{{ r.deleted_at?.split('T')[0] }}</td>
            <td>
                <button class="btn btn-secondary btn-xs" @click="restore(r.id)" style="margin-right:4px">恢复</button>
                <button class="btn btn-danger btn-xs" @click="permDelete(r.id)">永久删除</button>
            </td>
        </tr></tbody>
    </table>
    <div v-else class="empty-state">回收站为空</div>
</div>`,
    data() { return { items: [] }; },
    async mounted() { await this.load(); },
    methods: {
        async load() { try { this.items = await api('/recycle-bin/'); } catch(e) {} },
        async restore(id) {
            if (!confirm('确定恢复此记录吗？')) return;
            try { const res = await api('/recycle-bin/' + id + '/restore', { method: 'POST' }); this.showToast(res.message); await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async permDelete(id) {
            if (!confirm('永久删除后将无法恢复，确定吗？')) return;
            try { await api('/recycle-bin/' + id, { method: 'DELETE' }); this.showToast('已永久删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async clearAll() {
            if (!confirm('确定清空回收站吗？所有记录将永久删除！')) return;
            try { const res = await api('/recycle-bin/clear', { method: 'DELETE' }); this.showToast(res.message); await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        }
    }
};

// ---- Settings ----
const SettingsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>设置</h2></div>
    <div class="section-card">
        <h3 style="margin:0 0 12px 0">手头现金</h3>
        <p style="font-size:11px;color:var(--text-secondary);margin-bottom:12px">录入当前可用于还款的现金余额，用于现金流破裂预警和净值计算</p>
        <div class="form-row" style="gap:8px;align-items:flex-end">
            <div class="form-group" style="margin:0;flex:1">
                <label>当前余额</label>
                <input v-model.number="cashForm.amount" type="number" min="0" step="0.01" placeholder="0.00">
            </div>
            <div class="form-group" style="margin:0">
                <label>备注</label>
                <input v-model="cashForm.note" placeholder="如：6月工资到账">
            </div>
            <button class="btn btn-primary" @click="addCash" style="margin-bottom:12px">更新余额</button>
        </div>
        <div v-if="latestCash && latestCash.amount > 0" style="margin-top:8px;font-size:12px;color:var(--blue)">
            最近记录: ¥{{ fmt(latestCash.amount) }} ({{ latestCash.recorded_at }})
        </div>
        <div v-if="cashHistory.length > 0" style="margin-top:12px">
            <div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px">历史记录</div>
            <table class="data-table"><thead><tr><th>日期</th><th>金额</th><th>备注</th></tr></thead>
                <tbody><tr v-for="r in cashHistory" :key="r.id">
                    <td>{{ r.recorded_at }}</td><td style="color:var(--green)">¥{{ fmt(r.amount) }}</td><td>{{ r.note }}</td>
                </tr></tbody>
            </table>
        </div>
    </div>
    <div class="section-card">
        <h3 style="margin:0 0 12px 0">月度预算</h3>
        <div class="form-row" style="gap:8px;align-items:flex-end">
            <div class="form-group" style="margin:0;flex:1">
                <label>月预算金额</label>
                <input v-model.number="budgetForm.amount" type="number" min="0" step="100" placeholder="0">
            </div>
            <button class="btn btn-primary" @click="saveBudget" style="margin-bottom:12px">保存预算</button>
        </div>
        <div v-if="budgetAmount > 0" style="margin-top:8px;font-size:12px;color:var(--blue)">
            当前月预算: ¥{{ fmt(budgetAmount) }}
        </div>
    </div>
    <div class="section-card">
        <h3 style="margin:0 0 12px 0">数据安全</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-secondary" @click="exportData">导出 CSV</button>
            <button class="btn btn-secondary" @click="backupDB">备份数据库</button>
            <button class="btn btn-secondary" @click="cleanupData">清理冗余数据</button>
        </div>
    </div>
    <div class="section-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <h3 style="margin:0">数据管理</h3>
            <button class="btn btn-danger btn-sm" @click="clearAllData">清空所有财务数据</button>
        </div>
        <p style="font-size:11px;color:var(--text-secondary)">清空后需运行 python seed_finance_data.py 重新生成示例数据</p>
    </div>
    <div class="section-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <h3 style="margin:0">POS 费率配置</h3>
            <div class="form-row" style="gap:8px">
                <input v-model.number="feeForm.rate" type="number" step="0.0001" min="0" style="width:100px;padding:6px 10px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:12px">
                <button class="btn btn-primary btn-sm" @click="addFeeConfig">添加费率</button>
            </div>
        </div>
        <table class="data-table"><thead><tr><th>ID</th><th>费率</th><th>描述</th><th>状态</th><th>操作</th></tr></thead>
            <tbody><tr v-for="f in feeConfigs" :key="f.id">
                <td>{{ f.id }}</td><td>{{ (f.rate * 10000).toFixed(1) }}元/万 ({{ (f.rate * 100).toFixed(2) }}%)</td>
                <td>{{ f.description }}</td><td><span :class="'tag ' + (f.is_active ? 'green' : 'red')">{{ f.is_active ? '启用' : '禁用' }}</span></td>
                <td><button class="btn btn-danger btn-xs" @click="removeFee(f.id)">删除</button></td>
            </tr></tbody>
        </table>
    </div>
</div>`,
    data() { return { feeConfigs: [], feeForm: { fee_type: 'pos_swipe', rate: 0.006, description: '' }, cashForm: { amount: 0, note: '' }, latestCash: null, cashHistory: [], budgetForm: { amount: '' }, budgetAmount: 0 }; },
    async mounted() {
        try { this.feeConfigs = await api('/fee-configs/'); } catch(e) {}
        try { this.latestCash = await api('/settings/cash/latest'); } catch(e) {}
        try { this.cashHistory = await api('/settings/cash/history?limit=12'); } catch(e) {}
        try { const b = await api('/settings/app/budget'); this.budgetAmount = parseFloat(b.value) || 0; } catch(e) {}
    },
    methods: {
        fmt,
        async cleanupData() {
            if (!confirm('清理系统自动生成的冗余记录？')) return;
            try { const r = await api('/settings/cleanup', { method: 'POST' }); this.showToast(r.message || '清理完成'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async backupDB() {
            try { const r = await api('/settings/backup', { method: 'POST' }); this.showToast(r.message || '备份完成'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        exportData() {
            const token = getToken();
            const a = document.createElement('a');
            a.href = '/api/v1/finance/export/all';
            if (token) a.href += '?token=' + encodeURIComponent(token);
            // Use fetch to get the file with auth header
            fetch('/api/v1/finance/export/all', { headers: { 'Authorization': 'Bearer ' + token } })
                .then(r => r.blob()).then(blob => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = 'caizhiguanjia_export.csv';
                    a.click(); URL.revokeObjectURL(url);
                    this.showToast('导出成功');
                }).catch(e => this.showToast('导出失败', 'error'));
        },
        async saveBudget() {
            if (!this.budgetForm.amount && this.budgetForm.amount !== 0) return this.showToast('请输入预算金额', 'error');
            try { await api('/settings/app', { method: 'POST', body: JSON.stringify({ key: 'budget', value: String(this.budgetForm.amount) }) }); this.budgetAmount = this.budgetForm.amount; this.showToast('预算已保存'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async addCash() {
            if (!this.cashForm.amount) return this.showToast('请输入金额', 'error');
            try { await api('/settings/cash', { method: 'POST', body: JSON.stringify(this.cashForm) }); this.showToast('现金余额已更新'); this.cashForm.note = ''; this.latestCash = await api('/settings/cash/latest'); this.cashHistory = await api('/settings/cash/history?limit=12'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async addFeeConfig() {
            try { await api('/fee-configs/', { method: 'POST', body: JSON.stringify(this.feeForm) }); this.showToast('费率已添加'); this.feeConfigs = await api('/fee-configs/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async removeFee(id) { if (!confirm('确定删除?')) return; try { await api('/fee-configs/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.feeConfigs = await api('/fee-configs/'); } catch(e) { this.showToast(e.message, 'error'); } },
        async clearAllData() {
            if (!confirm('确定要清空所有财务数据吗？此操作不可撤销！\n\n建议：清空后可运行 python seed_finance_data.py 重新生成示例数据。')) return;
            try {
                const res = await api('/fee-configs/admin/clear-all', { method: 'DELETE' });
                this.showToast(res.message || '所有财务数据已清空');
            } catch(e) { this.showToast(e.message, 'error'); }
        }
    }
};

// ---- 404 Page ----
const NotFoundPage = {
    template: `
<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;text-align:center">
    <div style="font-size:72px;font-weight:bold;color:var(--red);margin-bottom:16px">404</div>
    <div style="font-size:18px;color:#888;margin-bottom:24px">页面未找到</div>
    <button class="btn btn-primary" @click="$router.push('/finance/dashboard')">返回仪表盘</button>
</div>`,
};

// ---- Simulator ----
const SimulatorPage = {
    mixins: [ToastMixin, ChartMixin],
    template: `
<div>
    <div class="page-header"><h2>债务模拟器</h2><p>情景分析、收入测算与风险评级</p></div>
    <div v-if="risk && risk.overall" class="stat-cards" style="margin-bottom:16px">
        <div class="stat-card v2-stat tooltip-card" :style="{ borderLeft: '3px solid ' + risk.overall.color }">
            <div class="label">综合风险评级</div>
            <span class="tooltip-text">5维加权评分: 生存线(25%) + 利息吞噬(25%) + 负债率(20%) + 现金流(15%) + 现金(15%)</span>
            <div class="value" :style="{ color: risk.overall.color }">{{ risk.overall.grade }}</div>
            <div style="font-size:12px;margin-top:4px" :style="{ color: risk.overall.color }">{{ risk.overall.label }}</div>
            <span class="v2-risk-badge" :style="{ background: risk.overall.color + '22', color: risk.overall.color, border: '1px solid ' + risk.overall.color + '44' }">评分 {{ risk.overall.score }}</span>
        </div>
        <div class="stat-card v2-stat tooltip-card" v-for="(d, k) in risk.dimensions" :key="k" :style="{ borderLeft: '3px solid ' + d.color }">
            <div class="label">{{ d.name }}</div>
            <div class="value" :style="{ color: d.color, fontSize: '18px' }">{{ d.grade }}</div>
            <span class="v2-risk-badge" :style="{ background: d.color + '22', color: d.color, border: '1px solid ' + d.color + '44' }">{{ d.label }}</span>
            <span class="tooltip-text">{{ dimTooltip(k, d) }}</span>
        </div>
    </div>

    <div class="section-title">收入模拟器</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">
        <span style="font-size:12px;color:#888">预设: 薪资</span>
        <span class="filter-chip" v-for="s in [12000,15000,18000,22000,30000]" :key="'s'+s" :class="{ active: simSalary === s }" @click="simSalary = s; loadPresets()">¥{{ s.toLocaleString() }}</span>
        <span style="font-size:12px;color:#888;margin-left:8px">副业</span>
        <span class="filter-chip" v-for="s in [1000,3000,5000,10000]" :key="'side'+s" :class="{ active: simSide === s }" @click="simSide = simSide === s ? 0 : s; loadPresets()">+¥{{ s.toLocaleString() }}</span>
        <span style="font-size:12px;color:#888;margin-left:8px">自定义</span>
        <input v-model.number="simSalary" type="number" style="width:100px;padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px" @change="loadPresets" placeholder="薪资">
        <input v-model.number="simSide" type="number" style="width:100px;padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px" @change="loadPresets" placeholder="副业">
    </div>
    <div class="chart-row" style="overflow-x:auto">
        <table class="data-table"><thead><tr>
            <th>类型</th><th>月收入</th>
            <th title="月收入 − 月支出 − 月利息，正值=止血">生存线</th>
            <th title="月利息 ÷ 月收入 × 100%，利息对收入的侵蚀程度">利息吞噬率</th>
            <th title="总负债 ÷ 生存线，按当前速度还清债务的月数">债务自由</th>
            <th title="生存线 × 12，一年能净还多少债务">年度净还债</th>
        </tr></thead>
            <tbody><tr v-for="(r, k) in presets" :key="k" :style="{ background: k.startsWith('salary') ? 'rgba(79,172,254,0.04)' : k.startsWith('side') ? 'rgba(249,202,36,0.04)' : k.startsWith('combo') ? 'rgba(0,210,160,0.04)' : '' }">
                <td>{{ r.type }}</td><td>{{ r.monthly_income }}</td>
                <td :style="{ color: r.survival_line < 0 ? 'var(--red)' : 'var(--green)' }">{{ r.survival_line >= 0 ? '+' : '' }}{{ fmt(r.survival_line) }}</td>
                <td :style="{ color: r.interest_rate > 40 ? 'var(--red)' : r.interest_rate > 20 ? 'var(--yellow)' : 'var(--green)' }">{{ r.interest_rate }}%</td>
                <td>{{ r.debt_freedom ? (r.debt_freedom >= 12 ? (r.debt_freedom/12).toFixed(1)+'年' : r.debt_freedom+'个月') : '无法还清' }}</td>
                <td :style="{ color: r.annual_repay < 0 ? 'var(--red)' : 'var(--green)' }">{{ r.annual_repay >= 0 ? '+' : '' }}¥{{ fmt(Math.abs(r.annual_repay)) }}</td>
            </tr></tbody>
        </table>
    </div>

    <div class="section-title">提前还款模拟</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">
        <span style="font-size:12px;color:#888">每月额外还款:</span>
        <span class="filter-chip" v-for="e in [1000,5000,10000]" :key="'e'+e" :class="{ active: extraPayment === e }" @click="extraPayment = extraPayment === e ? 0 : e; loadPresets()">+¥{{ e.toLocaleString() }}</span>
        <input v-model.number="extraPayment" type="number" style="width:100px;padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px" @change="loadPresets" placeholder="自定义">
    </div>
    <div class="chart-row" style="overflow-x:auto" v-if="extraPayment > 0">
        <table class="data-table"><thead><tr><th>额外月还款</th><th>新生存线</th><th>新债务自由</th><th>年度多还</th></tr></thead>
            <tbody><tr>
                <td style="color:var(--green)">+¥{{ extraPayment.toLocaleString() }}</td>
                <td :style="{ color: (extraEffect.new_survival_line < 0 ? 'var(--red)' : 'var(--green)') }">{{ extraEffect.new_survival_line >= 0 ? '+' : '' }}{{ fmt(extraEffect.new_survival_line) }}</td>
                <td>{{ extraEffect.new_debt_freedom ? (extraEffect.new_debt_freedom >= 12 ? (extraEffect.new_debt_freedom/12).toFixed(1)+'年' : extraEffect.new_debt_freedom+'个月') : '无法还清' }}</td>
                <td style="color:var(--green)">¥{{ fmt(extraEffect.annual_interest_saved) }}</td>
            </tr></tbody>
        </table>
    </div>
</div>`,
    data() { return { risk: null, presets: {}, simSalary: 0, simSide: 0, extraPayment: 0, extraEffect: {} }; },
    async mounted() {
        try { this.risk = await api('/v2/risk-assessment'); } catch(e) {}
        try { this.presets = await api('/v2/presets'); } catch(e) {}
    },
    methods: {
        fmt,
        dimTooltip(k, d) {
            const tips = {
                survival_line: '当前值 ¥' + (d.value || 0) + ' · 月收入−月支出−月利息 · 权重25% · 正值=止血',
                interest_consumption: '当前值 ' + (d.value || 0) + '% · 月利息÷月收入×100% · 权重25% · <15%健康 >30%高危',
                debt_ratio: '当前值 ' + (d.value || 0) + '% · 总负债÷月收入×100% · 权重20% · <50%健康 >80%高危',
                cash_flow: '当前值 ' + (d.value ? d.value + '个月' : '无风险') + ' · 手头现金÷|月缺口| · 权重15% · >12月安全 <3月高危',
                cash_on_hand: '当前值 ¥' + (d.value || 0) + ' · 手头可用现金余额 · 权重15% · 覆盖月开支越多越安全',
            };
            return tips[k] || '';
        },
        async loadPresets() {
            const params = [];
            if (this.simSalary) params.push('salary=' + this.simSalary);
            if (this.simSide) params.push('side_income=' + this.simSide);
            if (this.extraPayment) params.push('extra_payment=' + this.extraPayment);
            const url = '/v2/simulator' + (params.length ? '?' + params.join('&') : '');
            try { this.simResult = await api(url); this.extraEffect = this.simResult.extra_payment_effect || {}; } catch(e) {}
            try { this.presets = await api('/v2/presets'); } catch(e) {}
            try { this.risk = await api('/v2/risk-assessment'); } catch(e) {}
        },
    },
};

// ---- Routes ----
const routes = [
    { path: '/', redirect: '/finance/dashboard' },
    { path: '/finance/dashboard', component: DashboardPage },
    { path: '/finance/persons', component: PersonsPage },
    { path: '/finance/platforms', component: PlatformsPage },
    { path: '/finance/loans', component: LoansPage },
    { path: '/finance/pos', component: PosPage },
    { path: '/finance/credit-cards', component: CreditCardsPage },
    { path: '/finance/card-transactions', component: CardTransactionsPage },
    { path: '/finance/installments', component: InstallmentsPage },
    { path: '/finance/mortgages', component: MortgagesPage },
    { path: '/finance/incomes', component: IncomesPage },
    { path: '/finance/expenses', component: ExpensesPage },
    { path: '/finance/transactions', component: TransactionsPage },
    { path: '/finance/reports', component: ReportsPage },
    { path: '/finance/recycle-bin', component: RecycleBinPage },
    { path: '/finance/settings', component: SettingsPage },
    { path: '/finance/simulator', component: SimulatorPage },
    { path: '/finance/login', component: LoginPage },
    { path: '/:pathMatch(.*)*', component: NotFoundPage },
];

const router = VueRouter.createRouter({
    history: VueRouter.createWebHashHistory(),
    routes,
});

router.beforeEach((to, from) => {
    if (to.path === '/finance/login') return true;
    if (!getToken()) return '/finance/login';
    return true;
});

const App = {
    computed: {
        toast() { return sharedToast; },
        username() { return localStorage.getItem('finance_user') || ''; },
    },
    data() {
        return {
            currentPath: window.location.hash.slice(1) || '/finance/dashboard',
            navItems: [
                { path: '/finance/dashboard', label: '仪表盘', icon: '📊', hash: '#/finance/dashboard' },
                { path: '/finance/pos', label: 'POS 刷卡', icon: '💳', hash: '#/finance/pos' },
                { path: '/finance/loans', label: '借贷管理', icon: '💰', hash: '#/finance/loans' },
                { path: '/finance/credit-cards', label: '信用卡', icon: '🏦', hash: '#/finance/credit-cards' },
                { path: '/finance/card-transactions', label: '信用卡消费/还款', icon: '🛒', hash: '#/finance/card-transactions' },
                { path: '/finance/installments', label: '分期管理', icon: '📋', hash: '#/finance/installments' },
                { path: '/finance/mortgages', label: '房贷管理', icon: '🏠', hash: '#/finance/mortgages' },
                { path: '/finance/incomes', label: '收入管理', icon: '📈', hash: '#/finance/incomes' },
                { path: '/finance/expenses', label: '支出管理', icon: '📉', hash: '#/finance/expenses' },
                { path: '/finance/transactions', label: '统一流水', icon: '📜', hash: '#/finance/transactions' },
                { path: '/finance/reports', label: '统计报告', icon: '📊', hash: '#/finance/reports' },
                { path: '/finance/persons', label: '人员管理', icon: '👤', hash: '#/finance/persons' },
                { path: '/finance/platforms', label: '借贷平台', icon: '🏢', hash: '#/finance/platforms' },
                { path: '/finance/recycle-bin', label: '回收站', icon: '🗑️', hash: '#/finance/recycle-bin' },
                { path: '/finance/simulator', label: '债务模拟器', icon: '🔬', hash: '#/finance/simulator' },
                { path: '/finance/settings', label: '设置', icon: '⚙️', hash: '#/finance/settings' },
                { path: '/static/finance-help.html', label: '功能介绍', icon: '❓', hash: '/static/finance-help.html', external: true },
            ],
        };
    },
    methods: {
        navigate(path) {
            if ((this.navItems.find(i => i.path === path) || {}).external) {
                window.location.href = path;
                return;
            }
            this.currentPath = path;
            router.push(path);
        },
        logout() {
            clearToken();
            router.push('/finance/login');
        },
    },
    watch: {
        '$route'(to) { this.currentPath = to.path; }
    }
};

const vueApp = Vue.createApp(App);
vueApp.use(router);
vueApp.mount('#app');
