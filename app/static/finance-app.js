const BASE = '/api/v1/finance';

function fmt(n) { return n != null ? Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'; }
function fmtInt(n) { return n != null ? Number(n).toLocaleString('zh-CN') : '0'; }
function fmtDate(d) { return d ? d.split('T')[0] : ''; }
function daysLeft(d) { const diff = new Date(d) - new Date(); return Math.ceil(diff / 86400000); }

async function api(url, opts = {}) {
    const res = await fetch(BASE + url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    if (res.status === 204) return null;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
}

// ---- Global shared toast state ----
const sharedToast = Vue.reactive({ show: false, message: '', type: 'success' });

// ---- Toast mixin ----
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

// ---- Dashboard ----
const DashboardPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>仪表盘</h2><p>个人财务概览</p></div>
    <div class="stat-cards">
        <div class="stat-card"><div class="label">总负债</div><div class="value red">{{ fmt(dash.total_debt) }}</div></div>
        <div class="stat-card"><div class="label">总资产</div><div class="value green">{{ fmt(dash.total_assets) }}</div></div>
        <div class="stat-card"><div class="label">本月应付利息</div><div class="value yellow">{{ fmt(dash.monthly_interest) }}</div></div>
        <div class="stat-card"><div class="label">本月 POS 手续费</div><div class="value blue">{{ fmt(dash.monthly_pos_fee) }}</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-box"><div class="title">负债分布</div><div ref="pieChart" class="chart-inner"></div></div>
        <div class="chart-box"><div class="title">负债趋势（近12月快照）</div><div ref="trendChart" class="chart-inner"></div></div>
    </div>
    <div class="section-title">最近7天还款提醒</div>
    <div v-if="reminders.length === 0" class="empty-state">暂无到期提醒</div>
    <div v-for="r in reminders" :key="r.type + r.name" class="remind-item" :class="r.days_left <= 1 ? 'urgent' : r.days_left <= 3 ? 'warning' : 'normal'">
        <div><span :class="'badge ' + (r.type === 'loan' ? 'red' : r.type === 'card' ? 'blue' : 'yellow')">{{ r.type }}</span>
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
</div>`,
    data() {
        return { dash: {}, reminders: [], snapshots: [] };
    },
    async mounted() {
        try { this.dash = await api('/dashboard'); } catch(e) { this.showToast(e.message, 'error'); }
        try { this.reminders = await api('/repay-reminders'); } catch(e) {}
        try { this.snapshots = await api('/reports/snapshots?months=12'); } catch(e) {}
        this.$nextTick(() => { this.renderPie(); this.renderTrend(); this.renderGap(); });
    },
    methods: {
        fmt, fmtDate, daysLeft,
        renderPie() {
            const el = this.$refs.pieChart; if (!el) return;
            const chart = echarts.init(el);
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
            window.addEventListener('resize', () => chart.resize());
        },
        renderTrend() {
            const el = this.$refs.trendChart; if (!el) return;
            const chart = echarts.init(el);
            const dates = this.snapshots.map(s => s.snapshot_date);
            const data = this.snapshots.map(s => s.total_debt);
            if (dates.length === 0) { chart.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { color: '#888', fontSize: 13 } } }); return; }
            chart.setOption({
                tooltip: { trigger: 'axis' },
                grid: { left: 60, right: 20, top: 20, bottom: 30 },
                xAxis: { type: 'category', data: dates, axisLabel: { color: '#888', fontSize: 10, rotate: 30 } },
                yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => '¥' + (v/10000).toFixed(1) + 'w' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                series: [{ type: 'line', data, smooth: true, lineStyle: { color: '#e94560', width: 2 }, areaStyle: { color: 'rgba(233,69,96,0.1)' }, itemStyle: { color: '#e94560' } }]
            });
            window.addEventListener('resize', () => chart.resize());
        },
        renderGap() {
            const el = this.$refs.gapChart; if (!el) return;
            const chart = echarts.init(el);
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
                            return p[0].name + '<br/>收入: ¥' + fmt(d.total_income) + '<br/>支出: ¥' + fmt(d.total_expense) + '<br/>缺口: ¥' + fmt(d.gap);
                        }},
                        grid: { left: 60, right: 20, top: 20, bottom: 30 },
                        legend: { data: ['收入', '支出', '缺口'], textStyle: { color: '#888', fontSize: 11 }, top: 0 },
                        xAxis: { type: 'category', data: months, axisLabel: { color: '#888', fontSize: 10 } },
                        yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => '¥' + (v/10000).toFixed(1) + 'w' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                        series: [
                            { name: '收入', type: 'bar', data: results.map(r => r.total_income), itemStyle: { color: '#00d2a0' }, barGap: 0 },
                            { name: '支出', type: 'bar', data: results.map(r => r.total_expense), itemStyle: { color: '#e94560' } },
                            { name: '缺口', type: 'line', data: results.map(r => r.gap), lineStyle: { color: '#f9ca24' }, itemStyle: { color: '#f9ca24' }, symbol: 'diamond' },
                        ]
                    });
                });
            window.addEventListener('resize', () => chart.resize());
        }
    }
};

// ---- Persons page (for settings) ----
const PersonsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>人员管理</h2></div>
    <div class="section-card">
        <h3>添加人员</h3>
        <div class="form-row">
            <div class="form-group"><label>姓名</label><input v-model="form.name"></div>
            <div class="form-group"><label>关系</label><select v-model="form.relation"><option value="本人">本人</option><option value="配偶">配偶</option><option value="父母">父母</option><option value="子女">子女</option></select></div>
        </div>
        <button class="btn btn-primary" @click="create">添加</button>
    </div>
    <table class="data-table"><thead><tr><th>ID</th><th>姓名</th><th>关系</th><th>操作</th></tr></thead>
        <tbody><tr v-for="p in items" :key="p.id"><td>{{ p.id }}</td><td>{{ p.name }}</td><td><span class="tag blue">{{ p.relation }}</span></td><td><button class="btn btn-danger btn-xs" @click="remove(p.id)">删除</button></td></tr></tbody>
    </table>
</div>`,
    data() { return { form: { name: '', relation: '本人' }, items: [] }; },
    async mounted() { await this.load(); },
    methods: {
        async load() { try { this.items = await api('/persons/'); } catch(e) { this.showToast(e.message, 'error'); } },
        async create() {
            if (!this.form.name) return this.showToast('请输入姓名', 'error');
            try { await api('/persons/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('添加成功'); this.form.name = ''; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/persons/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Platforms page (for settings) ----
const PlatformsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>借贷平台</h2></div>
    <div class="section-card">
        <h3>添加平台</h3>
        <div class="form-row">
            <div class="form-group"><label>平台名称</label><input v-model="form.name"></div>
            <div class="form-group"><label>图标</label><input v-model="form.icon" placeholder="emoji或文字"></div>
        </div>
        <div class="form-group"><label>描述</label><input v-model="form.description"></div>
        <button class="btn btn-primary" @click="create">添加</button>
    </div>
    <table class="data-table"><thead><tr><th>ID</th><th>名称</th><th>图标</th><th>描述</th><th>操作</th></tr></thead>
        <tbody><tr v-for="p in items" :key="p.id"><td>{{ p.id }}</td><td>{{ p.name }}</td><td>{{ p.icon }}</td><td style='color:#888'>{{ p.description }}</td><td><button class="btn btn-danger btn-xs" @click="remove(p.id)">删除</button></td></tr></tbody>
    </table>
</div>`,
    data() { return { form: { name: '', icon: '', description: '' }, items: [] }; },
    async mounted() { await this.load(); },
    methods: {
        async load() { try { this.items = await api('/platforms/'); } catch(e) { this.showToast(e.message, 'error'); } },
        async create() {
            if (!this.form.name) return this.showToast('请输入平台名称', 'error');
            try { await api('/platforms/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('添加成功'); this.form = { name: '', icon: '', description: '' }; await this.load(); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/platforms/' + id, { method: 'DELETE' }); this.showToast('已删除'); await this.load(); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Loans ----
const LoansPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>借贷管理</h2><p>管理各平台借款及还款计划</p></div>
    <div class="filter-bar">
        <span class="filter-chip" :class="{ active: !filterPerson }" @click="filterPerson = null">全部</span>
        <span class="filter-chip" v-for="p in persons" :key="p.id" :class="{ active: filterPerson === p.id }" @click="filterPerson = p.id">{{ p.name }}</span>
    </div>
    <button class="btn btn-primary" @click="showModal = true" style="margin-bottom:12px">+ 新增借款</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>平台</th><th>金额</th><th>利率</th><th>方式</th><th>期数</th><th>状态</th><th>操作</th></tr></thead>
        <tbody><tr v-for="l in filteredLoans" :key="l.id">
            <td>{{ l.id }}</td><td>{{ l.person?.name || '-' }}</td><td>{{ l.platform?.name || '-' }}</td>
            <td>¥{{ fmt(l.amount) }}</td><td>{{ l.rate }} ({{ l.rate_type }})</td>
            <td><span class="tag blue">{{ l.repay_method }}</span></td><td>{{ l.periods }}</td>
            <td><span :class="'tag ' + (l.status === 'active' ? 'green' : 'red')">{{ l.status }}</span></td>
            <td><button class="btn btn-secondary btn-xs" @click="viewRepayments(l)" style="margin-right:4px">还款计划</button><button class="btn btn-danger btn-xs" @click="remove(l.id)">删除</button></td>
        </tr></tbody>
    </table>

    <!-- Create Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>新增借款</h3>
            <div class="form-row">
                <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
                <div class="form-group"><label>平台</label><select v-model="form.platform_id"><option v-for="p in platforms" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            </div>
            <div class="form-group"><label>借款金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01"></div>
            <div class="form-row">
                <div class="form-group"><label>利率</label><input v-model.number="form.rate" type="number" step="0.0001"></div>
                <div class="form-group"><label>利率类型</label><select v-model="form.rate_type"><option value="monthly">月利率</option><option value="annual">年利率</option><option value="total_interest">总利息反推</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>还款方式</label><select v-model="form.repay_method"><option value="equal_installment">等额本息</option><option value="interest_first">先息后本</option><option value="bullet">到期还本付息</option></select></div>
                <div class="form-group"><label>期数</label><input v-model.number="form.periods" type="number" min="1"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>开始日期</label><input v-model="form.start_date" type="date"></div>
                <div class="form-group"><label>结束日期</label><input v-model="form.end_date" type="date"></div>
            </div>
            <div class="form-group"><label>备注</label><input v-model="form.note"></div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="create">确认创建</button>
            </div>
        </div>
    </div>

    <!-- Repayments Modal -->
    <div v-if="repayLoan" class="modal-overlay" @click.self="repayLoan = null">
        <div class="modal" style="width:680px"><h3>还款计划 — 贷款 #{{ repayLoan.id }}</h3>
            <table class="data-table"><thead><tr><th>期数</th><th>到期日</th><th>本金</th><th>利息</th><th>总还款</th><th>状态</th><th>操作</th></tr></thead>
                <tbody><tr v-for="r in repayments" :key="r.id">
                    <td>{{ r.period_no }}</td><td>{{ r.due_date }}</td><td>¥{{ fmt(r.principal) }}</td><td>¥{{ fmt(r.interest) }}</td><td>¥{{ fmt(r.total_amount) }}</td>
                    <td><span :class="'tag ' + (r.status === 'paid' ? 'green' : 'yellow')">{{ r.status }}</span></td>
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
            showModal: false, repayLoan: null,
            form: { person_id: 1, platform_id: 1, amount: 0, rate: 0, rate_type: 'monthly', repay_method: 'equal_installment', periods: 12, start_date: '', end_date: '', note: '' }
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
        async create() {
            if (!this.form.amount || !this.form.periods) return this.showToast('请填写金额和期数', 'error');
            try {
                await api('/loans/', { method: 'POST', body: JSON.stringify(this.form) });
                this.showToast('借款创建成功，还款计划已自动生成');
                this.showModal = false;
                this.loans = await api('/loans/');
            } catch(e) { this.showToast(e.message, 'error'); }
        },
        async viewRepayments(loan) {
            this.repayLoan = loan;
            try { this.repayments = await api('/loans/' + loan.id + '/repayments'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async pay(rpId) {
            try { await api('/loans/repayments/' + rpId + '/pay', { method: 'PATCH' }); this.showToast('已标记还款'); this.repayments = await api('/loans/' + this.repayLoan.id + '/repayments'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/loans/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.loans = await api('/loans/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- POS Swipes ----
const PosPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>POS 刷卡</h2><p>管理 POS 机刷卡记录，自动计算手续费</p></div>
    <button class="btn btn-primary" @click="showModal = true" style="margin-bottom:12px">+ 新增刷卡</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>金额</th><th>费率</th><th>手续费</th><th>银行卡</th><th>POS机</th><th>刷卡时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="s in items" :key="s.id">
            <td>{{ s.id }}</td><td>{{ s.person?.name || '-' }}</td><td>¥{{ fmt(s.amount) }}</td><td>{{ (s.fee_rate * 10000).toFixed(1) }}元/万</td><td>¥{{ fmt(s.fee) }}</td>
            <td>{{ s.bank_card }}</td><td>{{ s.pos_machine }}</td><td>{{ fmtDate(s.swipe_date) }}</td>
            <td><button class="btn btn-danger btn-xs" @click="remove(s.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>新增刷卡记录</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>刷卡金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01"></div>
            <div class="form-group"><label>费率 (留空使用默认 60元/万)</label><input v-model.number="form.fee_rate" type="number" step="0.0001" placeholder="0.006"></div>
            <div class="form-row">
                <div class="form-group"><label>银行卡</label><input v-model="form.bank_card"></div>
                <div class="form-group"><label>POS机</label><input v-model="form.pos_machine"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>刷卡时间</label><input v-model="form.swipe_date" type="datetime-local"></div>
                <div class="form-group"><label>备注</label><input v-model="form.note"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="create">确认</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return {
            items: [], persons: [], showModal: false,
            form: { person_id: 1, amount: 0, fee_rate: null, bank_card: '', pos_machine: '', swipe_date: '', note: '' }
        };
    },
    async mounted() {
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.items = await api('/pos-swipes/'); } catch(e) {}
        if (this.persons.length) this.form.person_id = this.persons[0].id;
    },
    methods: {
        fmt, fmtDate,
        async create() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            const body = { ...this.form };
            if (body.fee_rate === '' || body.fee_rate === null || body.fee_rate === undefined) delete body.fee_rate;
            try { await api('/pos-swipes/', { method: 'POST', body: JSON.stringify(body) }); this.showToast('刷卡记录已添加'); this.showModal = false; this.items = await api('/pos-swipes/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/pos-swipes/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/pos-swipes/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Credit Cards ----
const CreditCardsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>信用卡管理</h2></div>
    <button class="btn btn-primary" @click="openCreate" style="margin-bottom:12px">+ 新增信用卡</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>银行</th><th>尾号</th><th>额度</th><th>已用额度</th><th>账单日</th><th>还款日</th><th>状态</th><th>操作</th></tr></thead>
        <tbody><tr v-for="c in items" :key="c.id">
            <td>{{ c.id }}</td><td>{{ c.person?.name || '-' }}</td><td>{{ c.bank }}</td><td>{{ c.card_number_last4 }}</td>
            <td>¥{{ fmt(c.credit_limit) }}</td><td :style="{ color: c.current_balance > 0 ? 'var(--red)' : '' }">¥{{ fmt(c.current_balance) }}</td>
            <td>每月{{ c.bill_day }}号</td><td>每月{{ c.due_day }}号</td>
            <td><span :class="'tag ' + (c.status === 'active' ? 'green' : 'red')">{{ c.status }}</span></td>
            <td><button class="btn btn-secondary btn-xs" @click="openEdit(c)" style="margin-right:4px">编辑</button><button class="btn btn-danger btn-xs" @click="remove(c.id)">删除</button></td>
        </tr></tbody>
    </table>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '编辑' : '新增' }}信用卡</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-row">
                <div class="form-group"><label>银行</label><input v-model="form.bank"></div>
                <div class="form-group"><label>卡号后四位</label><input v-model="form.card_number_last4" maxlength="4"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>信用额度</label><input v-model.number="form.credit_limit" type="number" min="0"></div>
                <div class="form-group"><label>当前已用额度</label><input v-model.number="form.current_balance" type="number" min="0"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>账单日（每月几号）</label><input v-model.number="form.bill_day" type="number" min="1" max="28"></div>
                <div class="form-group"><label>还款日（每月几号）</label><input v-model.number="form.due_day" type="number" min="1" max="28"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="editing ? update() : create()">{{ editing ? '保存' : '创建' }}</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], persons: [], showModal: false, editing: null, form: { person_id: 1, bank: '', card_number_last4: '', credit_limit: 0, current_balance: 0, bill_day: 1, due_day: 25 } };
    },
    async mounted() {
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.items = await api('/credit-cards/'); } catch(e) {}
        if (this.persons.length) this.form.person_id = this.persons[0].id;
    },
    methods: {
        fmt,
        openCreate() { this.editing = null; this.form = { person_id: this.persons[0]?.id || 1, bank: '', card_number_last4: '', credit_limit: 0, current_balance: 0, bill_day: 1, due_day: 25 }; this.showModal = true; },
        openEdit(c) { this.editing = c; this.form = { person_id: c.person_id, bank: c.bank, card_number_last4: c.card_number_last4, credit_limit: c.credit_limit, current_balance: c.current_balance, bill_day: c.bill_day, due_day: c.due_day }; this.showModal = true; },
        async create() {
            if (!this.form.bank || !this.form.card_number_last4) return this.showToast('请填写银行和卡号', 'error');
            try { await api('/credit-cards/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('信用卡已添加'); this.showModal = false; this.items = await api('/credit-cards/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async update() {
            try {
                await api('/credit-cards/' + this.editing.id, { method: 'PATCH', body: JSON.stringify({ credit_limit: this.form.credit_limit, current_balance: this.form.current_balance, bill_day: this.form.bill_day, due_day: this.form.due_day }) });
                this.showToast('已更新'); this.showModal = false; this.items = await api('/credit-cards/');
            } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/credit-cards/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/credit-cards/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Card Transactions ----
const CardTransactionsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>信用卡消费</h2><p>记录信用卡消费明细</p></div>
    <button class="btn btn-primary" @click="showModal = true" style="margin-bottom:12px">+ 新增消费</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>金额</th><th>描述</th><th>消费时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="t in items" :key="t.id">
            <td>{{ t.id }}</td><td>{{ t.person?.name || '-' }}</td><td>¥{{ fmt(t.amount) }}</td><td>{{ t.description }}</td><td>{{ fmtDate(t.trans_date) }}</td>
            <td><button class="btn btn-danger btn-xs" @click="remove(t.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>新增消费</h3>
            <div class="form-group"><label>信用卡</label><select v-model="form.card_id"><option v-for="c in cards" :key="c.id" :value="c.id">{{ c.bank }} 尾号{{ c.card_number_last4 }} ({{ c.person?.name }})</option></select></div>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01"></div>
            <div class="form-row">
                <div class="form-group"><label>描述</label><input v-model="form.description"></div>
                <div class="form-group"><label>消费时间</label><input v-model="form.trans_date" type="datetime-local"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="create">确认</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], cards: [], persons: [], showModal: false, form: { card_id: 1, person_id: 1, amount: 0, description: '', trans_date: '' } };
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
        async create() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            try { await api('/card-transactions/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('消费已记录'); this.showModal = false; this.items = await api('/card-transactions/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/card-transactions/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/card-transactions/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Installments ----
const InstallmentsPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>分期管理</h2><p>管理信用卡分期业务</p></div>
    <button class="btn btn-primary" @click="showModal = true" style="margin-bottom:12px">+ 新增分期</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>信用卡</th><th>金额</th><th>期数</th><th>每期费率</th><th>年化利率</th><th>每期还款</th><th>已还</th><th>操作</th></tr></thead>
        <tbody><tr v-for="i in items" :key="i.id">
            <td>{{ i.id }}</td><td>{{ i.person?.name || '-' }}</td><td>{{ i.card_id }}</td>
            <td>¥{{ fmt(i.amount) }}</td><td>{{ i.periods }}</td><td>{{ (i.period_rate * 100).toFixed(2) }}%</td>
            <td><span class="tag yellow">{{ i.annual_rate ? (i.annual_rate * 100).toFixed(2) + '%' : '-' }}</span></td>
            <td>¥{{ fmt(i.period_total) }}</td><td>{{ i.paid_periods }}/{{ i.periods }}</td>
            <td><button class="btn btn-secondary btn-xs" @click="payPeriod(i)" style="margin-right:4px">还一期</button><button class="btn btn-danger btn-xs" @click="remove(i.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>新增分期</h3>
            <div class="form-group"><label>信用卡</label><select v-model="form.card_id"><option v-for="c in cards" :key="c.id" :value="c.id">{{ c.bank }} 尾号{{ c.card_number_last4 }}</option></select></div>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>分期金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01"></div>
            <div class="form-row">
                <div class="form-group"><label>期数</label><input v-model.number="form.periods" type="number" min="1"></div>
                <div class="form-group"><label>每期手续费率</label><input v-model.number="form.period_rate" type="number" step="0.0001" placeholder="0.006 = 0.6%"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>开始日期</label><input v-model="form.start_date" type="date"></div>
                <div class="form-group"><label>备注</label><input v-model="form.note"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="create">确认创建</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], cards: [], persons: [], showModal: false, form: { card_id: 1, person_id: 1, amount: 0, periods: 12, period_rate: 0.006, start_date: '', note: '' } };
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
        async create() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            try { await api('/card-installments/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('分期已创建'); this.showModal = false; this.items = await api('/card-installments/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async payPeriod(inst) {
            try { await api('/card-installments/' + inst.id + '/pay-period', { method: 'PATCH' }); this.showToast('已还一期'); this.items = await api('/card-installments/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/card-installments/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/card-installments/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Mortgages ----
const MortgagesPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>房贷管理</h2></div>
    <button class="btn btn-primary" @click="showModal = true" style="margin-bottom:12px">+ 新增房贷</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>银行</th><th>房产</th><th>总金额</th><th>剩余本金</th><th>年利率</th><th>月供</th><th>状态</th><th>操作</th></tr></thead>
        <tbody><tr v-for="m in items" :key="m.id">
            <td>{{ m.id }}</td><td>{{ m.person?.name || '-' }}</td><td>{{ m.bank }}</td><td>{{ m.house_name }}</td>
            <td>¥{{ fmt(m.total_amount) }}</td><td :style="{ color: 'var(--red)' }">¥{{ fmt(m.remaining_principal) }}</td>
            <td>{{ (m.rate * 100).toFixed(2) }}%</td><td>¥{{ fmt(m.monthly_payment) }}</td>
            <td><span :class="'tag ' + (m.status === 'active' ? 'green' : 'red')">{{ m.status }}</span></td>
            <td><button class="btn btn-secondary btn-xs" @click="openEdit(m)" style="margin-right:4px">更新本金</button><button class="btn btn-danger btn-xs" @click="remove(m.id)">删除</button></td>
        </tr></tbody>
    </table>

    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>{{ editing ? '更新剩余本金' : '新增房贷' }}</h3>
            <template v-if="!editing">
                <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
                <div class="form-row">
                    <div class="form-group"><label>银行</label><input v-model="form.bank"></div>
                    <div class="form-group"><label>房产名称</label><input v-model="form.house_name"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>贷款总额</label><input v-model.number="form.total_amount" type="number" min="0"></div>
                    <div class="form-group"><label>剩余本金</label><input v-model.number="form.remaining_principal" type="number" min="0"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>年利率</label><input v-model.number="form.rate" type="number" step="0.0001"></div>
                    <div class="form-group"><label>月供</label><input v-model.number="form.monthly_payment" type="number" min="0"></div>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>开始日期</label><input v-model="form.start_date" type="date"></div>
                    <div class="form-group"><label>结束日期</label><input v-model="form.end_date" type="date"></div>
                </div>
                <div class="form-group"><label>总期数</label><input v-model.number="form.total_periods" type="number" min="1"></div>
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
</div>`,
    data() {
        return { items: [], persons: [], showModal: false, editing: null, editPrincipal: 0, form: { person_id: 1, bank: '', house_name: '', total_amount: 0, remaining_principal: 0, rate: 0.04, start_date: '', end_date: '', total_periods: 360, monthly_payment: 0, repay_method: 'equal_installment' } };
    },
    async mounted() {
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.items = await api('/mortgages/'); } catch(e) {}
        if (this.persons.length) this.form.person_id = this.persons[0].id;
    },
    methods: {
        fmt,
        openEdit(m) { this.editing = m; this.editPrincipal = m.remaining_principal; this.showModal = true; },
        async create() {
            if (!this.form.bank || !this.form.total_amount) return this.showToast('请填写必填项', 'error');
            try { await api('/mortgages/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('房贷已添加'); this.showModal = false; this.items = await api('/mortgages/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async updatePrincipal() {
            try { await api('/mortgages/' + this.editing.id + '?remaining_principal=' + this.editPrincipal, { method: 'PATCH' }); this.showToast('本金已更新'); this.showModal = false; this.editing = null; this.items = await api('/mortgages/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/mortgages/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/mortgages/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Incomes ----
const IncomesPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>收入管理</h2><p>记录每月/年度/一次性收入</p></div>
    <button class="btn btn-primary" @click="showModal = true" style="margin-bottom:12px">+ 新增收入</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>金额</th><th>来源</th><th>类型</th><th>周期</th><th>操作</th></tr></thead>
        <tbody><tr v-for="i in items" :key="i.id">
            <td>{{ i.id }}</td><td>{{ i.person?.name || '-' }}</td><td style="color:var(--green)">¥{{ fmt(i.amount) }}</td><td>{{ i.source }}</td>
            <td><span class="tag blue">{{ i.period_type }}</span></td><td>{{ i.period_value }}</td>
            <td><button class="btn btn-danger btn-xs" @click="remove(i.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>新增收入</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01"></div>
            <div class="form-group"><label>来源</label><input v-model="form.source" placeholder="工资/兼职/投资/租金/其他"></div>
            <div class="form-row">
                <div class="form-group"><label>类型</label><select v-model="form.period_type"><option value="monthly">月度</option><option value="yearly">年度</option><option value="once">一次性</option></select></div>
                <div class="form-group"><label>周期 (如 2025-05)</label><input v-model="form.period_value" placeholder="2025-05"></div>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
                <button class="btn btn-secondary" @click="showModal = false">取消</button>
                <button class="btn btn-primary" @click="create">确认</button>
            </div>
        </div>
    </div>
</div>`,
    data() {
        return { items: [], persons: [], showModal: false, form: { person_id: 1, amount: 0, source: '', period_type: 'monthly', period_value: new Date().toISOString().slice(0, 7), note: '' } };
    },
    async mounted() {
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.items = await api('/incomes/'); } catch(e) {}
        if (this.persons.length) this.form.person_id = this.persons[0].id;
    },
    methods: {
        fmt,
        async create() {
            if (!this.form.amount || !this.form.source) return this.showToast('请填写金额和来源', 'error');
            try { await api('/incomes/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('收入已记录'); this.showModal = false; this.items = await api('/incomes/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/incomes/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/incomes/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Expenses ----
const ExpensesPage = {
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>支出管理</h2><p>记录日常消费支出</p></div>
    <div class="filter-bar">
        <span class="filter-chip" :class="{ active: !filterCat }" @click="filterCat = null">全部</span>
        <span class="filter-chip" v-for="c in cats" :key="c" :class="{ active: filterCat === c }" @click="filterCat = c">{{ c }}</span>
    </div>
    <button class="btn btn-primary" @click="showModal = true" style="margin-bottom:12px">+ 新增支出</button>
    <table class="data-table"><thead><tr><th>ID</th><th>人员</th><th>金额</th><th>分类</th><th>周期</th><th>日期</th><th>备注</th><th>操作</th></tr></thead>
        <tbody><tr v-for="e in filteredExpenses" :key="e.id">
            <td>{{ e.id }}</td><td>{{ e.person?.name || '-' }}</td><td style="color:var(--red)">¥{{ fmt(e.amount) }}</td>
            <td><span class="tag yellow">{{ e.category }}</span></td><td>{{ e.period_value }}</td><td>{{ e.expense_date }}</td>
            <td style="color:#888;font-size:11px">{{ e.note }}</td>
            <td><button class="btn btn-danger btn-xs" @click="remove(e.id)">删除</button></td>
        </tr></tbody>
    </table>
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal"><h3>新增支出</h3>
            <div class="form-group"><label>人员</label><select v-model="form.person_id"><option v-for="p in persons" :key="p.id" :value="p.id">{{ p.name }}</option></select></div>
            <div class="form-group"><label>金额</label><input v-model.number="form.amount" type="number" min="0" step="0.01"></div>
            <div class="form-row">
                <div class="form-group"><label>分类</label><select v-model="form.category"><option v-for="c in cats" :key="c" :value="c">{{ c }}</option></select></div>
                <div class="form-group"><label>周期</label><input v-model="form.period_value" placeholder="2025-05"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>日期</label><input v-model="form.expense_date" type="date"></div>
                <div class="form-group"><label>备注</label><input v-model="form.note"></div>
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
        return { items: [], persons: [], cats, filterCat: null, showModal: false, form: { person_id: 1, amount: 0, category: '餐饮', period_value: new Date().toISOString().slice(0, 7), expense_date: new Date().toISOString().slice(0, 10), note: '' } };
    },
    async mounted() {
        try { this.persons = await api('/persons/'); } catch(e) {}
        try { this.items = await api('/expenses/'); } catch(e) {}
        if (this.persons.length) this.form.person_id = this.persons[0].id;
    },
    computed: {
        filteredExpenses() { return this.filterCat ? this.items.filter(e => e.category === this.filterCat) : this.items; }
    },
    methods: {
        fmt,
        async create() {
            if (!this.form.amount) return this.showToast('请输入金额', 'error');
            try { await api('/expenses/', { method: 'POST', body: JSON.stringify(this.form) }); this.showToast('支出已记录'); this.showModal = false; this.items = await api('/expenses/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async remove(id) { if (!confirm('确定删除?')) return; try { await api('/expenses/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.items = await api('/expenses/'); } catch(e) { this.showToast(e.message, 'error'); } }
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
        <input type="date" v-model="filter.date_from" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px">
        <span style="color:#888;font-size:11px">至</span>
        <input type="date" v-model="filter.date_to" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:140px">
        <button class="btn btn-secondary btn-sm" @click="load">查询</button>
    </div>
    <table class="data-table"><thead><tr><th>ID</th><th>类型</th><th>金额</th><th>时间</th></tr></thead>
        <tbody><tr v-for="t in items" :key="t.type + t.id">
            <td>{{ t.id }}</td>
            <td><span :class="'tag ' + typeColor(t.type)">{{ t.type }}</span></td>
            <td :style="{ color: t.type === 'expense' || t.type === 'card_trans' ? 'var(--red)' : 'var(--green)' }">¥{{ fmt(t.amount) }}</td>
            <td style="color:#888">{{ t.created_at }}</td>
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
            types: [{ label: '贷款', value: 'loan' }, { label: 'POS', value: 'pos' }, { label: '分期', value: 'installment' }, { label: '信用卡', value: 'card_trans' }, { label: '收入', value: 'income' }, { label: '支出', value: 'expense' }],
            filter: { type: null, date_from: null, date_to: null }
        };
    },
    async mounted() { await this.load(); },
    methods: {
        fmt,
        typeColor(t) { const m = { loan: 'red', pos: 'blue', installment: 'yellow', card_trans: 'red', income: 'green', expense: 'red' }; return m[t] || ''; },
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
    mixins: [ToastMixin],
    template: `
<div>
    <div class="page-header"><h2>统计报告</h2><p>多维度财务数据分析</p></div>
    <div class="stat-cards" style="margin-bottom:16px">
        <div class="stat-card"><div class="label">活跃贷款总额</div><div class="value red">{{ fmt(summary.total_active_loans) }}</div></div>
        <div class="stat-card"><div class="label">累计POS手续费</div><div class="value blue">{{ fmt(summary.total_pos_fees) }}</div></div>
    </div>
    <div class="chart-row">
        <div class="chart-box"><div class="title">各平台贷款分布</div><div ref="platformChart" class="chart-inner"></div></div>
        <div class="chart-box"><div class="title">月度POS手续费</div><div ref="monthChart" class="chart-inner"></div></div>
    </div>
    <div class="section-title">收支缺口分析</div>
    <div class="filter-bar">
        <input v-model.number="gapYear" type="number" min="2020" max="2100" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:80px" placeholder="年份">
        <input v-model.number="gapMonth" type="number" min="1" max="12" style="padding:4px 8px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;width:80px" placeholder="月份(可选)">
        <button class="btn btn-secondary btn-sm" @click="loadGap">分析</button>
    </div>
    <div v-if="gap" :class="'gap-box ' + (gap.gap < 0 ? 'negative' : 'positive')">
        <div style="font-size:12px;color:#888;margin-bottom:4px">{{ gap.period }} 收支缺口</div>
        <div :style="{ fontSize: '28px', fontWeight: 'bold', color: gap.gap < 0 ? 'var(--red)' : 'var(--green)' }">¥{{ fmt(Math.abs(gap.gap)) }}</div>
        <div style="font-size:13px;color:#888;margin-top:4px">{{ gap.gap < 0 ? '入不敷出' : '收支有盈余' }}</div>
        <div style="display:flex;justify-content:center;gap:24px;margin-top:12px;font-size:12px;color:#888">
            <div>收入: <span style="color:var(--green)">¥{{ fmt(gap.total_income) }}</span></div>
            <div>支出: <span style="color:var(--red)">¥{{ fmt(gap.total_expense) }}</span></div>
            <div>还款: <span style="color:var(--yellow)">¥{{ fmt(gap.debt_payment) }}</span></div>
        </div>
    </div>
</div>`,
    data() {
        return { summary: { total_active_loans: 0, total_pos_fees: 0 }, platformData: [], monthData: [], gap: null, gapYear: new Date().getFullYear(), gapMonth: null };
    },
    async mounted() {
        try { this.summary = await api('/reports/summary'); } catch(e) {}
        try { this.platformData = await api('/reports/by-platform'); } catch(e) {}
        try { this.monthData = await api('/reports/by-month'); } catch(e) {}
        await this.loadGap();
        this.$nextTick(() => { this.renderPlatform(); this.renderMonth(); });
    },
    methods: {
        fmt,
        async loadGap() {
            try { this.gap = await api('/reports/gap-analysis?year=' + this.gapYear + (this.gapMonth ? '&month=' + this.gapMonth : '')); } catch(e) {}
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
            chart.setOption({
                tooltip: { trigger: 'axis' },
                grid: { left: 60, right: 20, top: 20, bottom: 30 },
                xAxis: { type: 'category', data: this.monthData.map(d => d.month), axisLabel: { color: '#888', fontSize: 10 } },
                yAxis: { type: 'value', axisLabel: { color: '#888', fontSize: 10, formatter: v => '¥' + v }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                series: [{ type: 'bar', data: this.monthData.map(d => d.pos_fee), itemStyle: { color: '#4facfe', borderRadius: [4,4,0,0] } }]
            });
            window.addEventListener('resize', () => chart.resize());
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
    data() { return { feeConfigs: [], feeForm: { fee_type: 'pos_swipe', rate: 0.006, description: '' } }; },
    async mounted() { try { this.feeConfigs = await api('/fee-configs/'); } catch(e) {} },
    methods: {
        async addFeeConfig() {
            try { await api('/fee-configs/', { method: 'POST', body: JSON.stringify(this.feeForm) }); this.showToast('费率已添加'); this.feeConfigs = await api('/fee-configs/'); } catch(e) { this.showToast(e.message, 'error'); }
        },
        async removeFee(id) { if (!confirm('确定删除?')) return; try { await api('/fee-configs/' + id, { method: 'DELETE' }); this.showToast('已删除'); this.feeConfigs = await api('/fee-configs/'); } catch(e) { this.showToast(e.message, 'error'); } }
    }
};

// ---- Router Setup ----
const routes = [
    { path: '/', redirect: '/finance/dashboard' },
    { path: '/finance/dashboard', component: DashboardPage },
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
    { path: '/finance/settings', component: SettingsPage },
];

const router = VueRouter.createRouter({
    history: VueRouter.createWebHashHistory(),
    routes,
});

const App = {
    computed: {
        toast() { return sharedToast; },
    },
    data() {
        return {
            currentPath: window.location.hash.slice(1) || '/finance/dashboard',
            navItems: [
                { path: '/finance/dashboard', label: '仪表盘', icon: '📊', hash: '#/finance/dashboard' },
                { path: '/finance/loans', label: '借贷管理', icon: '💰', hash: '#/finance/loans' },
                { path: '/finance/pos', label: 'POS 刷卡', icon: '💳', hash: '#/finance/pos' },
                { path: '/finance/credit-cards', label: '信用卡', icon: '🏦', hash: '#/finance/credit-cards' },
                { path: '/finance/card-transactions', label: '信用卡消费', icon: '🛒', hash: '#/finance/card-transactions' },
                { path: '/finance/installments', label: '分期管理', icon: '📋', hash: '#/finance/installments' },
                { path: '/finance/mortgages', label: '房贷管理', icon: '🏠', hash: '#/finance/mortgages' },
                { path: '/finance/incomes', label: '收入管理', icon: '📈', hash: '#/finance/incomes' },
                { path: '/finance/expenses', label: '支出管理', icon: '📉', hash: '#/finance/expenses' },
                { path: '/finance/transactions', label: '统一流水', icon: '📜', hash: '#/finance/transactions' },
                { path: '/finance/reports', label: '统计报告', icon: '📊', hash: '#/finance/reports' },
                { path: '/finance/settings', label: '设置', icon: '⚙️', hash: '#/finance/settings' },
            ],
        };
    },
    methods: {
        navigate(path) {
            this.currentPath = path;
            router.push(path);
        },
    },
    watch: {
        '$route'(to) { this.currentPath = to.path; }
    }
};

const vueApp = Vue.createApp(App);
vueApp.use(router);
vueApp.mount('#app');
