"""
ORM 数据模型 — 定义所有数据库表结构

使用 SQLAlchemy 2.0 的 DeclarativeBase 声明式映射：
- 一个 Python 类 = 一张数据库表
- 类属性 = 表中的列（字段）
- relationship() = 表之间的关联关系

模型关系总览:
    User 1──N Article (作者)
    User N──M Role (用户角色，通过 user_roles 关联表)
    Category 1──N Article (分类)
    Article N──M Tag (文章标签，通过 article_tags 关联表)
    Role N──M Permission (角色权限，通过 role_permissions 关联表)
    User 1──N Media (上传者)
"""
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.db import Base

# ========== 多对多关联表 ==========
# SQLAlchemy 中多对多关系需要中间表，只定义列信息，不需要单独建类

article_tags = Table(
    "article_tags",
    Base.metadata,
    Column("article_id", ForeignKey("articles.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id"), primary_key=True),
)


# ========== 用户模型 ==========
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)  # 登录名，唯一
    email = Column(String(120), unique=True, nullable=False)                 # 邮箱，唯一
    full_name = Column(String(100), default="")                              # 显示名称
    hashed_password = Column(String, nullable=False)                         # bcrypt 哈希密码
    is_active = Column(Boolean, default=True)                                # 是否激活（软删除标记）
    is_superuser = Column(Boolean, default=False)                            # 超级管理员标记
    created_at = Column(DateTime, default=datetime.utcnow)

    # foreign_keys 指定关联的外键列（因为 Article 表有两个指向 users 的 FK）
    articles = relationship("Article", back_populates="author", foreign_keys="[Article.author_id]")
    media = relationship("Media", back_populates="uploader")
    roles = relationship("Role", secondary=user_roles, back_populates="users")


# ========== 文章模型 ==========
class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)   # 文章标题
    slug = Column(String(200), index=True)                     # URL 友好标识（自动从标题生成）
    content = Column(Text, default="")                         # 正文内容
    excerpt = Column(String(300), default="")                  # 摘要/摘录
    status = Column(String(20), default="draft", index=True)   # 状态: draft/pending/published/archived
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 审核人 ID
    review_comment = Column(Text, default="")                              # 审核意见
    published_at = Column(DateTime, nullable=True)                         # 发布时间
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时自动更新时间

    # foreign_keys 必须显式指定，因为有两列都指向 users.id
    author = relationship("User", foreign_keys=[author_id], back_populates="articles")
    category = relationship("Category", back_populates="articles")
    tags = relationship("Tag", secondary=article_tags, back_populates="articles")


# ========== 分类模型 ==========
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)   # 分类名称（唯一）
    slug = Column(String(50), unique=True)                    # URL 友好标识
    description = Column(String(200), default="")            # 分类描述

    articles = relationship("Article", back_populates="category")


# ========== 标签模型 ==========
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(30), unique=True, nullable=False)   # 标签名（唯一）
    slug = Column(String(30), unique=True)                    # URL 友好标识

    articles = relationship("Article", secondary=article_tags, back_populates="tags")


# ========== 媒体文件模型 ==========
class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)        # 存储文件名（UUID 生成）
    original_name = Column(String, nullable=False)   # 原始文件名
    file_path = Column(String, nullable=False)       # 服务器存储路径
    file_size = Column(Integer, default=0)           # 文件大小（字节）
    mime_type = Column(String(100))                  # MIME 类型（如 image/png）
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    uploader = relationship("User", back_populates="media")


# ========== 角色模型 ==========
class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(30), unique=True, nullable=False)   # 角色名: admin / editor / author
    description = Column(String(100), default="")            # 角色描述

    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")


# ========== 权限模型 ==========
class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)     # 权限名称（给人看的）
    code = Column(String(50), unique=True, nullable=False)   # 权限编码（给程序判断用的，唯一）
    description = Column(String(100), default="")

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


# ========== 财务管理模块模型 ==========

class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    relation = Column(String(20), default="本人")
    created_at = Column(DateTime, default=datetime.utcnow)


class LoanPlatform(Base):
    __tablename__ = "loan_platforms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    icon = Column(String(10), default="")
    description = Column(String(200), default="")


class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("loan_platforms.id"), nullable=False)
    amount = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    rate_type = Column(String(10), nullable=False)
    total_interest = Column(Float, nullable=True)
    repay_method = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    periods = Column(Integer, nullable=False)
    status = Column(String(20), default="active")
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    _paid_periods = Column("paid_periods", Integer, default=0)

    person = relationship("Person")
    platform = relationship("LoanPlatform")
    repayments = relationship("RepaymentPlan", back_populates="loan", cascade="all, delete-orphan")

    @property
    def paid_periods(self):
        # 优先用已还期数（手动保存或自动计算），其次用还款计划中已还的数量
        from_plans = sum(1 for rp in self.repayments if rp.status == "paid")
        return max(self._paid_periods, from_plans)

    @paid_periods.setter
    def paid_periods(self, value):
        self._paid_periods = value

    @property
    def remaining_periods(self):
        return self.periods - self.paid_periods


class RepaymentPlan(Base):
    __tablename__ = "repayment_plans"
    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    period_no = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    principal = Column(Float, nullable=False)
    interest = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), default="pending")
    paid_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    loan = relationship("Loan", back_populates="repayments")
    person = relationship("Person")


class PosSwipe(Base):
    __tablename__ = "pos_swipes"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=True)
    amount = Column(Float, nullable=False)
    fee_rate = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    bank_card = Column(String(50), default="")
    pos_machine = Column(String(50), default="")
    swipe_date = Column(DateTime, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    card = relationship("CreditCard")


class CreditCard(Base):
    __tablename__ = "credit_cards"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    bank = Column(String(50), nullable=False)
    card_number_last4 = Column(String(4), nullable=False)
    credit_limit = Column(Float, nullable=False)
    current_balance = Column(Float, default=0)
    interest_rate = Column(Float, default=0.1825)  # 年化透支利率，默认日息万分之五
    bill_day = Column(Integer, nullable=False)
    due_day = Column(Integer, nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    installments = relationship("CardInstallment", back_populates="card", cascade="all, delete-orphan")
    transactions = relationship("CreditCardTransaction", back_populates="card", cascade="all, delete-orphan")


class CreditCardTransaction(Base):
    __tablename__ = "credit_card_transactions"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    trans_type = Column(String(10), default="消费")  # 消费 / 还款
    description = Column(String(200), default="")
    trans_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    card = relationship("CreditCard", back_populates="transactions")


class CreditCardBill(Base):
    """信用卡月度账单"""
    __tablename__ = "credit_card_bills"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=False)
    bill_month = Column(String(7), nullable=False)
    bill_start = Column(Date, nullable=False)
    bill_end = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    bill_amount = Column(Float, default=0)
    paid_amount = Column(Float, default=0)
    min_payment = Column(Float, default=0)
    interest = Column(Float, default=0)
    fee = Column(Float, default=0)
    status = Column(String(20), default="unpaid")
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("CreditCard", backref="bills")


class CardInstallment(Base):
    __tablename__ = "card_installments"
    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    periods = Column(Integer, nullable=False)
    period_rate = Column(Float, nullable=False)
    annual_rate = Column(Float, nullable=True)
    total_fee = Column(Float, nullable=False)
    period_principal = Column(Float, nullable=False)
    period_fee = Column(Float, nullable=False)
    period_total = Column(Float, nullable=False)
    paid_periods = Column(Integer, default=0)
    start_date = Column(Date, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")
    card = relationship("CreditCard", back_populates="installments")

    @property
    def remaining_periods(self):
        return self.periods - self.paid_periods


class Mortgage(Base):
    __tablename__ = "mortgages"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    bank = Column(String(50), nullable=False)
    house_name = Column(String(100), default="")
    total_amount = Column(Float, nullable=False)
    remaining_principal = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_periods = Column(Integer, nullable=False)
    monthly_payment = Column(Float, nullable=False)
    repay_method = Column(String(20), default="equal_installment")
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")


class Income(Base):
    __tablename__ = "incomes"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    source = Column(String(50), nullable=False)
    period_type = Column(String(10), nullable=False)
    period_value = Column(String(7), nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(30), nullable=False)
    period_value = Column(String(7), nullable=False)
    expense_date = Column(Date, nullable=False)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person")


class FeeConfig(Base):
    __tablename__ = "fee_configs"
    id = Column(Integer, primary_key=True, index=True)
    fee_type = Column(String(30), nullable=False)
    rate = Column(Float, nullable=False)
    description = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DebtSnapshot(Base):
    __tablename__ = "debt_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    total_debt = Column(Float, default=0)
    loan_debt = Column(Float, default=0)
    card_debt = Column(Float, default=0)
    installment_debt = Column(Float, default=0)
    mortgage_debt = Column(Float, default=0)
    pos_fee_total = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeletedRecord(Base):
    """回收站：存储被删除的记录，支持恢复。"""
    __tablename__ = "deleted_records"
    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(50), nullable=False)
    record_id = Column(Integer, nullable=False)
    record_data = Column(Text, nullable=False)
    deleted_at = Column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    """应用设置键值表"""
    __tablename__ = "app_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(500), default="")


class CashRecord(Base):
    """手头现金记录：用户手动录入的现金余额，支持历史追踪。"""
    __tablename__ = "cash_records"
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    recorded_at = Column(Date, nullable=False, default=date.today, index=True)
    note = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
