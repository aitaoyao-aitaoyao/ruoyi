"""
Pydantic 请求/响应模型 — 定义 API 的数据结构

Pydantic 是 FastAPI 的数据验证库，作用：
1. 自动校验请求体格式（类型检查、必填字段、长度限制等）
2. 自动生成 Swagger 文档中的请求/响应示例
3. 使用 model_config = {"from_attributes": True} 实现 ORM 对象与 Pydantic 的互转

Pydantic v2 关键语法:
    - field_validator("字段名")     →  自定义字段校验规则
    - model_config                  →  替代 v1 的 class Config
    - from_attributes=True          →  允许从 ORM 对象直接转换（v1 叫 orm_mode）
    - Optional[X]                   →  可选字段，可以为 None
    - EmailStr                      →  自动校验邮箱格式
"""
from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# ========== 认证相关 ==========

class Token(BaseModel):
    """登录成功后返回的令牌"""
    access_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """刷新令牌请求"""
    access_token: str


class UserCreate(BaseModel):
    """用户注册请求"""
    username: str
    email: EmailStr              # EmailStr 自动校验邮箱格式
    full_name: str = ""
    password: str

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v):
        """校验用户名长度：至少 2 个字符"""
        if len(v.strip()) < 2:
            raise ValueError("用户名至少需要 2 个字符")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v):
        """校验密码长度：至少 4 个字符"""
        if len(v) < 4:
            raise ValueError("密码至少需要 4 个字符")
        return v


class UserRead(BaseModel):
    """用户信息响应（不含密码）"""
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    roles: list[str] = []

    model_config = {"from_attributes": True}  # 允许从 ORM User 对象直接转换


class UserUpdate(BaseModel):
    """个人资料更新请求（所有字段可选，只更新传了的字段）"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str


# ========== 分类相关 ==========

class CategoryCreate(BaseModel):
    """创建分类请求"""
    name: str
    description: str = ""


class CategoryRead(BaseModel):
    """分类信息响应"""
    id: int
    name: str
    slug: str
    description: str

    model_config = {"from_attributes": True}


# ========== 标签相关 ==========

class TagCreate(BaseModel):
    """创建标签请求"""
    name: str


class TagRead(BaseModel):
    """标签信息响应（含关联文章数）"""
    id: int
    name: str
    slug: str
    article_count: int = 0  # 使用此标签的文章数量

    model_config = {"from_attributes": True}


# ========== 文章相关 ==========

class ArticleCreate(BaseModel):
    """创建文章请求"""
    title: str
    content: str = ""
    excerpt: str = ""
    category_id: Optional[int] = None
    tag_ids: list[int] = []

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        """校验标题：不能是空字符串"""
        if not v.strip():
            raise ValueError("标题不能为空")
        return v.strip()


class ArticleUpdate(BaseModel):
    """更新文章请求（所有字段可选）"""
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    category_id: Optional[int] = None
    tag_ids: Optional[list[int]] = None


class ArticleRead(BaseModel):
    """文章详情响应（含作者、分类、标签等关联信息）"""
    id: int
    title: str
    slug: str
    content: str
    excerpt: str
    status: str
    category_id: Optional[int] = None
    category_name: str = ""
    author_id: int
    author_name: str = ""
    tags: list[TagRead] = []
    review_comment: str = ""
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArticleListResponse(BaseModel):
    """文章列表响应（分页）"""
    items: list[ArticleRead]
    total: int
    page: int
    size: int


# ========== 媒体文件相关 ==========

class MediaRead(BaseModel):
    """媒体文件信息响应"""
    id: int
    filename: str
    original_name: str
    file_size: int
    mime_type: str
    uploader_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaListResponse(BaseModel):
    """媒体文件列表响应（分页）"""
    items: list[MediaRead]
    total: int
    page: int
    size: int


# ========== 用户管理相关（管理员） ==========

class UserAdminCreate(UserCreate):
    """管理员创建用户请求（继承注册模型，增加角色分配）"""
    role_ids: list[int] = []


class UserAdminUpdate(BaseModel):
    """管理员更新用户请求"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[list[int]] = None


# ========== 仪表盘相关 ==========

class DashboardStats(BaseModel):
    """仪表盘统计数据"""
    total_articles: int
    published_articles: int
    pending_articles: int
    draft_articles: int
    total_users: int
    total_categories: int
    total_tags: int
    total_media: int


class RecentActivity(BaseModel):
    """最近活动"""
    id: int
    title: str
    status: str
    author_name: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class RejectRequest(BaseModel):
    """驳回文章请求"""
    comment: str = ""


# ========== 财务管理模块 Schemas ==========


class PersonCreate(BaseModel):
    name: str
    relation: str = "本人"


class PersonRead(BaseModel):
    id: int
    name: str
    relation: str
    created_at: datetime
    model_config = {"from_attributes": True}


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    relation: Optional[str] = None


class LoanPlatformCreate(BaseModel):
    name: str
    icon: str = ""
    description: str = ""


class LoanPlatformRead(BaseModel):
    id: int
    name: str
    icon: str
    description: str
    model_config = {"from_attributes": True}


class LoanPlatformUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None


class LoanCreate(BaseModel):
    person_id: int
    platform_id: int
    amount: float
    rate: float
    rate_type: str
    total_interest: Optional[float] = None
    repay_method: str
    start_date: date
    end_date: Optional[date] = None
    periods: int
    note: str = ""

    @field_validator("rate_type")
    @classmethod
    def validate_rate_type(cls, v):
        if v not in ("monthly", "annual", "total_interest"):
            raise ValueError("rate_type must be monthly, annual, or total_interest")
        return v

    @field_validator("repay_method")
    @classmethod
    def validate_repay_method(cls, v):
        if v not in ("equal_installment", "interest_first", "bullet", "flexible"):
            raise ValueError("repay_method must be equal_installment, interest_first, bullet, or flexible")
        return v

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("借款金额必须大于 0")
        return v


class LoanRead(BaseModel):
    id: int
    person_id: int
    platform_id: int
    amount: float
    rate: float
    rate_type: str
    total_interest: Optional[float] = None
    repay_method: str
    start_date: date
    end_date: date
    periods: int
    paid_periods: int = 0
    remaining_periods: int = 0
    status: str
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    platform: Optional[LoanPlatformRead] = None
    model_config = {"from_attributes": True}


class LoanUpdate(BaseModel):
    person_id: Optional[int] = None
    platform_id: Optional[int] = None
    amount: Optional[float] = None
    rate: Optional[float] = None
    rate_type: Optional[str] = None
    repay_method: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    periods: Optional[int] = None
    paid_periods: Optional[int] = None
    status: Optional[str] = None
    note: Optional[str] = None


class RepaymentPlanRead(BaseModel):
    id: int
    loan_id: int
    person_id: int
    period_no: int
    due_date: date
    principal: float
    interest: float
    total_amount: float
    status: str
    paid_date: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class PosSwipeCreate(BaseModel):
    person_id: int
    card_id: Optional[int] = None
    amount: float
    fee_rate: Optional[float] = None
    bank_card: str = ""
    pos_machine: str = ""
    swipe_date: datetime
    note: str = ""

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("金额必须大于 0")
        return v


class PosSwipeRead(BaseModel):
    id: int
    person_id: int
    card_id: Optional[int] = None
    amount: float
    fee_rate: float
    fee: float
    bank_card: str
    pos_machine: str
    swipe_date: datetime
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class PosSwipeUpdate(BaseModel):
    card_id: Optional[int] = None
    amount: Optional[float] = None
    fee_rate: Optional[float] = None
    bank_card: Optional[str] = None
    pos_machine: Optional[str] = None
    swipe_date: Optional[datetime] = None
    note: Optional[str] = None


class CreditCardCreate(BaseModel):
    person_id: int
    bank: str
    card_number_last4: str
    credit_limit: float
    current_balance: float = 0
    interest_rate: float = 0.1825  # 年化透支利率，默认万分之五
    bill_day: int
    due_day: int

    @field_validator("bill_day")
    @classmethod
    def validate_bill_day(cls, v):
        if v < 1 or v > 28:
            raise ValueError("bill_day must be 1-28")
        return v

    @field_validator("due_day")
    @classmethod
    def validate_due_day(cls, v):
        if v < 1 or v > 28:
            raise ValueError("due_day must be 1-28")
        return v

    @field_validator("credit_limit")
    @classmethod
    def credit_limit_positive(cls, v):
        if v <= 0:
            raise ValueError("信用额度必须大于 0")
        return v


class CreditCardRead(BaseModel):
    id: int
    person_id: int
    bank: str
    card_number_last4: str
    credit_limit: float
    current_balance: float
    interest_rate: float
    bill_day: int
    due_day: int
    status: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class CreditCardUpdate(BaseModel):
    credit_limit: Optional[float] = None
    current_balance: Optional[float] = None
    interest_rate: Optional[float] = None
    bill_day: Optional[int] = None
    due_day: Optional[int] = None
    status: Optional[str] = None


class CreditCardTransactionCreate(BaseModel):
    card_id: int
    person_id: int
    amount: float
    trans_type: str = "消费"  # 消费 / 还款
    description: str = ""
    trans_date: datetime


class CreditCardTransactionRead(BaseModel):
    id: int
    card_id: int
    person_id: int
    amount: float
    trans_type: str
    description: str
    trans_date: datetime
    created_at: datetime
    person: Optional[PersonRead] = None
    card: Optional[CreditCardRead] = None
    model_config = {"from_attributes": True}


class CreditCardTransactionUpdate(BaseModel):
    card_id: Optional[int] = None
    amount: Optional[float] = None
    trans_type: Optional[str] = None
    description: Optional[str] = None
    trans_date: Optional[datetime] = None


class CardInstallmentCreate(BaseModel):
    card_id: int
    person_id: int
    amount: float
    periods: int
    rate_type: str = "period_rate"  # period_rate / annual_rate / total_fee
    rate_value: float = 0.0  # the rate value according to rate_type
    start_date: date
    note: str = ""

    @field_validator("rate_type")
    @classmethod
    def validate_rate_type(cls, v):
        if v not in ("period_rate", "annual_rate", "total_fee"):
            raise ValueError("rate_type must be period_rate, annual_rate, or total_fee")
        return v


class CardInstallmentRead(BaseModel):
    id: int
    card_id: int
    person_id: int
    amount: float
    periods: int
    period_rate: float
    annual_rate: Optional[float] = None
    total_fee: float
    period_principal: float
    period_fee: float
    period_total: float
    paid_periods: int
    remaining_periods: int = 0
    start_date: date
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    card: Optional[CreditCardRead] = None
    model_config = {"from_attributes": True}


class CardInstallmentUpdate(BaseModel):
    amount: Optional[float] = None
    periods: Optional[int] = None
    paid_periods: Optional[int] = None
    start_date: Optional[date] = None
    note: Optional[str] = None


class MortgageCreate(BaseModel):
    person_id: int
    bank: str
    house_name: str = ""
    total_amount: float
    remaining_principal: float
    rate: float
    start_date: date
    end_date: Optional[date] = None
    total_periods: int
    monthly_payment: float
    repay_method: str = "equal_installment"

    @field_validator("total_amount")
    @classmethod
    def total_amount_positive(cls, v):
        if v <= 0:
            raise ValueError("贷款总额必须大于 0")
        return v


class MortgageRead(BaseModel):
    id: int
    person_id: int
    bank: str
    house_name: str
    total_amount: float
    remaining_principal: float
    rate: float
    start_date: date
    end_date: date
    total_periods: int
    monthly_payment: float
    repay_method: str
    status: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class MortgageUpdate(BaseModel):
    person_id: Optional[int] = None
    bank: Optional[str] = None
    house_name: Optional[str] = None
    total_amount: Optional[float] = None
    remaining_principal: Optional[float] = None
    rate: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_periods: Optional[int] = None
    monthly_payment: Optional[float] = None
    repay_method: Optional[str] = None
    status: Optional[str] = None


class IncomeCreate(BaseModel):
    person_id: int
    amount: float
    source: str
    period_type: str
    period_value: str
    note: str = ""

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("金额必须大于 0")
        return v


class IncomeRead(BaseModel):
    id: int
    person_id: int
    amount: float
    source: str
    period_type: str
    period_value: str
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class IncomeUpdate(BaseModel):
    person_id: Optional[int] = None
    amount: Optional[float] = None
    source: Optional[str] = None
    period_type: Optional[str] = None
    period_value: Optional[str] = None
    note: Optional[str] = None


class ExpenseCreate(BaseModel):
    person_id: int
    amount: float
    category: str
    period_value: str
    expense_date: date
    note: str = ""

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("金额必须大于 0")
        return v


class ExpenseRead(BaseModel):
    id: int
    person_id: int
    amount: float
    category: str
    period_value: str
    expense_date: date
    note: str
    created_at: datetime
    person: Optional[PersonRead] = None
    model_config = {"from_attributes": True}


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = None
    category: Optional[str] = None
    period_value: Optional[str] = None
    expense_date: Optional[date] = None
    note: Optional[str] = None


class FeeConfigCreate(BaseModel):
    fee_type: str
    rate: float
    description: str = ""


class CreditCardBillCreate(BaseModel):
    card_id: int
    bill_amount: Optional[float] = 0
    paid_amount: Optional[float] = 0
    interest: Optional[float] = 0
    fee: Optional[float] = 0
    note: str = ""


class CreditCardBillUpdate(BaseModel):
    bill_amount: Optional[float] = None
    paid_amount: Optional[float] = None
    interest: Optional[float] = None
    fee: Optional[float] = None
    status: Optional[str] = None
    note: Optional[str] = None


class CreditCardBillRead(BaseModel):
    id: int
    card_id: int
    bill_month: str
    bill_start: date
    bill_end: date
    due_date: date
    bill_amount: float
    paid_amount: float
    min_payment: float
    interest: float
    fee: float
    status: str
    note: str
    created_at: datetime
    model_config = {"from_attributes": True}


class FeeConfigRead(BaseModel):
    id: int
    fee_type: str
    rate: float
    description: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class DebtSnapshotRead(BaseModel):
    id: int
    snapshot_date: date
    total_debt: float
    loan_debt: float
    card_debt: float
    installment_debt: float
    mortgage_debt: float
    pos_fee_total: float
    created_at: datetime
    model_config = {"from_attributes": True}


class TransactionQuery(BaseModel):
    type: Optional[str] = None
    person_id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = 1
    page_size: int = 20


class DashboardSummary(BaseModel):
    total_debt: float
    total_debt_ex_mortgage: float
    total_assets: float
    monthly_interest: float
    monthly_pos_fee: float
    total_loan_debt: float
    total_card_debt: float
    total_installment_debt: float
    total_mortgage_debt: float


class RepayReminderItem(BaseModel):
    type: str
    name: str
    person_name: str
    card_last4: str
    due_date: date
    amount: float
    days_left: int


class GapAnalysis(BaseModel):
    period_value: str
    total_income: float
    daily_expense: float
    debt_payment: float
    total_expense: float
    gap: float


class CashRecordCreate(BaseModel):
    amount: float
    recorded_at: Optional[date] = None
    note: str = ""

    @field_validator("amount")
    @classmethod
    def amount_non_negative(cls, v):
        if v < 0:
            raise ValueError("金额不能为负数")
        return v


class CashRecordRead(BaseModel):
    id: int
    amount: float
    recorded_at: date
    note: str
    created_at: datetime
    model_config = {"from_attributes": True}
