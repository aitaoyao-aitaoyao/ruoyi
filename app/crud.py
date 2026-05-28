"""
CRUD 操作层 — 封装所有数据库增删改查逻辑

CRUD = Create(创建) / Read(读取) / Update(更新) / Delete(删除)

设计原则:
    - 每个函数接收 db: Session 作为第一个参数（由 FastAPI 依赖注入）
    - 使用 SQLAlchemy 的查询构建器 (query.filter.order_by.offset.limit)
    - 所有写操作需要 db.commit() 才能持久化到磁盘
    - db.refresh() 用于获取数据库生成的默认值（如 id、created_at）
"""
import re
import unicodedata
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import User, Article, Category, Tag, Media, Role, Permission
from app.models import Person, LoanPlatform, Loan, RepaymentPlan, PosSwipe, CreditCard
from app.models import CreditCardTransaction, CardInstallment, Mortgage, Income, Expense, FeeConfig, DebtSnapshot, DeletedRecord
from app import schemas
from app.auth import hash_password
from app.finance.calc_engine import calc_installment_annual_rate


def slugify(text: str) -> str:
    """
    将任意文本转换为 URL 友好的 slug 格式。

    处理步骤:
        1. 将 Unicode 字符标准化（如 é → e）
        2. 移除非 ASCII 字符
        3. 去除非字母数字字符
        4. 转小写，空格/连字符统一为 -

    示例:
        "Hello World!" → "hello-world"
        "Python 学习"  → "python"
    """
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


# ======================== 用户 CRUD ========================

def get_user(db: Session, user_id: int) -> Optional[User]:
    """根据 ID 查询单个用户，找不到返回 None"""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """根据用户名查询用户（登录时使用）"""
    return db.query(User).filter(User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 20) -> list[User]:
    """分页查询用户列表"""
    return db.query(User).offset(skip).limit(limit).all()


def count_users(db: Session) -> int:
    """统计用户总数"""
    return db.query(User).count()


def create_user(db: Session, user_in: schemas.UserCreate) -> User:
    """
    创建新用户。
    密码会在存入数据库前进行 bcrypt 哈希处理。
    """
    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hash_password(user_in.password),  # 密码哈希，不存明文
    )
    db.add(user)       # 添加到会话（暂未写入数据库）
    db.commit()        # 提交事务（写入数据库）
    db.refresh(user)   # 刷新对象（获取数据库生成的 id 等字段）
    return user


# ======================== 文章 CRUD ========================

def get_articles(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    tag: Optional[str] = None,
    keyword: Optional[str] = None,
    author_id: Optional[int] = None,
) -> list[Article]:
    """
    多条件查询文章列表（支持分页和多种筛选条件）。

    参数说明:
        skip:        跳过的记录数（分页偏移）
        limit:       返回的最大记录数
        status:      按状态筛选 (draft/pending/published/archived)
        category_id: 按分类 ID 筛选
        tag:         按标签名筛选
        keyword:     按关键词搜索（模糊匹配标题和正文）
        author_id:   按作者 ID 筛选

    查询构建采用"链式调用"模式：逐步添加过滤条件，最后统一执行。
    这种模式比拼接 SQL 字符串更安全（防止 SQL 注入）。
    """
    q = db.query(Article)

    # 动态构建查询条件：有值才添加过滤
    if status:
        q = q.filter(Article.status == status)
    if category_id is not None:
        q = q.filter(Article.category_id == category_id)
    if author_id is not None:
        q = q.filter(Article.author_id == author_id)
    if keyword:
        # ilike 是大小写不敏感的 LIKE（SQLite 中与 LIKE 相同）
        kw = f"%{keyword}%"
        q = q.filter(
            (Article.title.ilike(kw)) | (Article.content.ilike(kw))
        )
    if tag:
        # any() 用于多对多关系的条件查询
        q = q.filter(Article.tags.any(Tag.name == tag))

    q = q.order_by(Article.updated_at.desc())  # 按更新时间倒序
    return q.offset(skip).limit(limit).all()


def count_articles(
    db: Session,
    *,
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    tag: Optional[str] = None,
    keyword: Optional[str] = None,
    author_id: Optional[int] = None,
) -> int:
    """
    统计符合条件的文章总数（与 get_articles 使用相同的筛选条件）。
    分页接口需要同时返回数据列表和总数，前端才能渲染页码。
    """
    q = db.query(Article)
    if status:
        q = q.filter(Article.status == status)
    if category_id is not None:
        q = q.filter(Article.category_id == category_id)
    if author_id is not None:
        q = q.filter(Article.author_id == author_id)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            (Article.title.ilike(kw)) | (Article.content.ilike(kw))
        )
    if tag:
        q = q.filter(Article.tags.any(Tag.name == tag))
    return q.count()


def get_article(db: Session, article_id: int) -> Optional[Article]:
    """根据 ID 查询单篇文章"""
    return db.query(Article).filter(Article.id == article_id).first()


def create_article(db: Session, article_in: schemas.ArticleCreate, author_id: int) -> Article:
    """
    创建新文章。自动处理：
    - 从标题生成唯一 slug（重复时追加数字后缀）
    - 关联标签
    - 初始状态设为 draft
    """
    # 生成唯一 slug
    slug = slugify(article_in.title)
    base_slug = slug
    counter = 1
    # 如果 slug 已存在，追加数字后缀直到唯一
    while db.query(Article).filter(Article.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    article = Article(
        title=article_in.title,
        slug=slug,
        content=article_in.content,
        excerpt=article_in.excerpt,
        category_id=article_in.category_id,
        author_id=author_id,
        status="draft",  # 新建文章默认为草稿状态
    )
    # 关联标签（多对多关系）
    if article_in.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(article_in.tag_ids)).all()
        article.tags = tags

    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def update_article(
    db: Session, article: Article, update_in: schemas.ArticleUpdate
) -> Article:
    """
    更新文章字段（部分更新：只修改传入的字段）。

    关键技巧：
        用 is not None 而非 if value 判断，
        因为空字符串 "" 和 0 也是有效值，不能用 if 过滤掉。
        用 Optional 的类型声明配合 is not None 实现精确的部分更新。
    """
    if update_in.title is not None:
        article.title = update_in.title
        # 标题变了，重新生成 slug
        slug = slugify(update_in.title)
        base_slug = slug
        counter = 1
        while (
            db.query(Article)
            .filter(Article.slug == slug, Article.id != article.id)  # 排除自身
            .first()
        ):
            slug = f"{base_slug}-{counter}"
            counter += 1
        article.slug = slug

    if update_in.content is not None:
        article.content = update_in.content
    if update_in.excerpt is not None:
        article.excerpt = update_in.excerpt
    if update_in.category_id is not None:
        article.category_id = update_in.category_id
    if update_in.tag_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(update_in.tag_ids)).all()
        article.tags = tags  # 直接用新列表替换旧的关联

    db.commit()
    db.refresh(article)
    return article


def delete_article(db: Session, article: Article):
    """物理删除文章（从数据库中移除）"""
    db.delete(article)
    db.commit()


# ======================== 文章工作流操作 ========================
# 文章状态机: draft → pending → published → archived
#              ↑          ↓
#              └── reject ─┘

def submit_article(db: Session, article: Article) -> Article:
    """作者提交审核：draft → pending"""
    article.status = "pending"
    db.commit()
    db.refresh(article)
    return article


def approve_article(db: Session, article: Article, reviewer_id: int) -> Article:
    """编辑审核通过：pending → published（记录审核人和发布时间）"""
    article.status = "published"
    article.reviewed_by = reviewer_id
    article.published_at = datetime.utcnow()
    db.commit()
    db.refresh(article)
    return article


def reject_article(
    db: Session, article: Article, reviewer_id: int, comment: str = ""
) -> Article:
    """编辑驳回：pending → draft（记录审核人和驳回意见）"""
    article.status = "draft"
    article.reviewed_by = reviewer_id
    article.review_comment = comment
    db.commit()
    db.refresh(article)
    return article


def publish_article(db: Session, article: Article) -> Article:
    """编辑直接发布（跳过审核流程，draft/pending → published）"""
    article.status = "published"
    article.published_at = datetime.utcnow()
    db.commit()
    db.refresh(article)
    return article


def archive_article(db: Session, article: Article) -> Article:
    """归档文章：published → archived"""
    article.status = "archived"
    db.commit()
    db.refresh(article)
    return article


# ======================== 分类 CRUD ========================

def get_categories(db: Session) -> list[Category]:
    """获取全部分类（按名称排序）"""
    return db.query(Category).order_by(Category.name).all()


def get_category(db: Session, category_id: int) -> Optional[Category]:
    """根据 ID 查询分类"""
    return db.query(Category).filter(Category.id == category_id).first()


def create_category(db: Session, cat_in: schemas.CategoryCreate) -> Category:
    """创建新分类（自动生成 slug）"""
    cat = Category(
        name=cat_in.name,
        slug=slugify(cat_in.name),
        description=cat_in.description,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, category: Category):
    """删除分类"""
    db.delete(category)
    db.commit()


# ======================== 标签 CRUD ========================

def get_tags(db: Session) -> list[Tag]:
    """获取全部标签（按名称排序）"""
    return db.query(Tag).order_by(Tag.name).all()


def get_tag(db: Session, tag_id: int) -> Optional[Tag]:
    """根据 ID 查询标签"""
    return db.query(Tag).filter(Tag.id == tag_id).first()


def create_tag(db: Session, tag_in: schemas.TagCreate) -> Tag:
    """创建新标签（自动生成 slug）"""
    tag = Tag(name=tag_in.name, slug=slugify(tag_in.name))
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag: Tag):
    """删除标签"""
    db.delete(tag)
    db.commit()


# ======================== 媒体文件 CRUD ========================

def get_media_list(db: Session, skip: int = 0, limit: int = 20) -> list[Media]:
    """分页查询媒体文件列表（按上传时间倒序）"""
    return (
        db.query(Media)
        .order_by(Media.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_media(db: Session) -> int:
    """统计媒体文件总数"""
    return db.query(Media).count()


def get_media(db: Session, media_id: int) -> Optional[Media]:
    """根据 ID 查询媒体文件"""
    return db.query(Media).filter(Media.id == media_id).first()


def create_media(
    db: Session,
    filename: str,
    original_name: str,
    file_path: str,
    file_size: int,
    mime_type: str,
    uploader_id: int,
) -> Media:
    """记录上传的媒体文件信息到数据库"""
    media = Media(
        filename=filename,
        original_name=original_name,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        uploader_id=uploader_id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media


def delete_media(db: Session, media: Media):
    """删除媒体文件记录"""
    db.delete(media)
    db.commit()


# ======================== 角色 CRUD ========================

def get_roles(db: Session) -> list[Role]:
    """获取全部角色"""
    return db.query(Role).all()


def get_role(db: Session, role_id: int) -> Optional[Role]:
    """根据 ID 查询角色"""
    return db.query(Role).filter(Role.id == role_id).first()


# ======================== 仪表盘 ========================

def get_dashboard_stats(db: Session) -> dict:
    """
    获取仪表盘统计数据。
    返回各项计数，前端用于渲染统计卡片。
    """
    return {
        "total_articles": db.query(Article).count(),
        "published_articles": db.query(Article)
        .filter(Article.status == "published")
        .count(),
        "pending_articles": db.query(Article)
        .filter(Article.status == "pending")
        .count(),
        "draft_articles": db.query(Article)
        .filter(Article.status == "draft")
        .count(),
        "total_users": db.query(User).count(),
        "total_categories": db.query(Category).count(),
        "total_tags": db.query(Tag).count(),
        "total_media": db.query(Media).count(),
    }


def get_recent_articles(db: Session, limit: int = 5) -> list[Article]:
    """获取最近更新的文章（按更新时间倒序）"""
    return (
        db.query(Article)
        .order_by(Article.updated_at.desc())
        .limit(limit)
        .all()
    )


# ======================== 财务管理 CRUD ========================

# --- Person ---
def create_person(db: Session, data: schemas.PersonCreate) -> Person:
    person = Person(**data.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person

def get_persons(db: Session) -> list[Person]:
    return db.query(Person).all()

def get_person(db: Session, person_id: int) -> Optional[Person]:
    return db.query(Person).filter(Person.id == person_id).first()

def update_person(db: Session, person_id: int, data: schemas.PersonUpdate) -> Optional[Person]:
    obj = db.query(Person).filter(Person.id == person_id).first()
    if obj:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, val)
        db.commit()
        db.refresh(obj)
    return obj

def delete_person(db: Session, person_id: int) -> bool:
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        return False
    _save_deleted_record(db, "persons", person.id, _serialize_record(person))
    db.delete(person)
    db.commit()
    return True


# --- LoanPlatform ---
def create_platform(db: Session, data: schemas.LoanPlatformCreate) -> LoanPlatform:
    platform = LoanPlatform(**data.model_dump())
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform

def get_platforms(db: Session) -> list[LoanPlatform]:
    return db.query(LoanPlatform).all()

def get_platform(db: Session, platform_id: int) -> Optional[LoanPlatform]:
    return db.query(LoanPlatform).filter(LoanPlatform.id == platform_id).first()

def update_platform(db: Session, platform_id: int, data: schemas.LoanPlatformUpdate) -> Optional[LoanPlatform]:
    obj = db.query(LoanPlatform).filter(LoanPlatform.id == platform_id).first()
    if obj:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, val)
        db.commit()
        db.refresh(obj)
    return obj

def delete_platform(db: Session, platform_id: int) -> bool:
    platform = db.query(LoanPlatform).filter(LoanPlatform.id == platform_id).first()
    if not platform:
        return False
    _save_deleted_record(db, "loan_platforms", platform.id, _serialize_record(platform))
    db.delete(platform)
    db.commit()
    return True


# --- Loan ---
def create_loan(db: Session, data: schemas.LoanCreate, repayments: list[dict]) -> Loan:
    loan = Loan(**data.model_dump())
    db.add(loan)
    db.flush()
    for rp in repayments:
        plan = RepaymentPlan(loan_id=loan.id, person_id=data.person_id, **rp)
        db.add(plan)
    db.commit()
    db.refresh(loan)
    return loan

def get_loans(db: Session, person_id: Optional[int] = None) -> list[Loan]:
    q = db.query(Loan)
    if person_id:
        q = q.filter(Loan.person_id == person_id)
    return q.order_by(Loan.created_at.desc()).all()

def get_loan(db: Session, loan_id: int) -> Optional[Loan]:
    return db.query(Loan).filter(Loan.id == loan_id).first()

def update_loan(db: Session, loan_id: int, data: schemas.LoanUpdate) -> Optional[Loan]:
    obj = db.query(Loan).filter(Loan.id == loan_id).first()
    if obj:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, val)
        db.commit()
        db.refresh(obj)
    return obj

def update_loan_status(db: Session, loan_id: int, status: str) -> Optional[Loan]:
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if loan:
        loan.status = status
        db.commit()
        db.refresh(loan)
    return loan

def delete_loan(db: Session, loan_id: int) -> bool:
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        return False
    _save_deleted_record(db, "loans", loan.id, _serialize_record(loan))
    db.delete(loan)
    db.commit()
    return True


# --- RepaymentPlan ---
def get_repayments(db: Session, loan_id: int) -> list[RepaymentPlan]:
    return db.query(RepaymentPlan).filter(RepaymentPlan.loan_id == loan_id).order_by(RepaymentPlan.period_no).all()

def pay_repayment(db: Session, repayment_id: int) -> Optional[RepaymentPlan]:
    rp = db.query(RepaymentPlan).filter(RepaymentPlan.id == repayment_id).first()
    if rp:
        rp.status = "paid"
        rp.paid_date = datetime.utcnow()
        db.commit()
        db.refresh(rp)
    return rp


def delete_repayments_for_loan(db: Session, loan_id: int) -> int:
    """Delete all repayment plans for a loan. Returns count of deleted rows."""
    count = db.query(RepaymentPlan).filter(RepaymentPlan.loan_id == loan_id).delete()
    db.commit()
    return count


# --- PosSwipe ---
def create_pos_swipe(db: Session, data: schemas.PosSwipeCreate, fee: float = 0) -> PosSwipe:
    swipe = PosSwipe(**data.model_dump(), fee=fee)
    db.add(swipe)
    # 关联信用卡：刷卡金额增加该卡的已用额度
    if data.card_id:
        card = db.query(CreditCard).filter(CreditCard.id == data.card_id).first()
        if card:
            card.current_balance = round((card.current_balance or 0) + data.amount, 2)
    db.commit()
    db.refresh(swipe)
    return swipe

def get_pos_swipes(db: Session, person_id: Optional[int] = None) -> list[PosSwipe]:
    q = db.query(PosSwipe)
    if person_id:
        q = q.filter(PosSwipe.person_id == person_id)
    return q.order_by(PosSwipe.swipe_date.desc()).all()

def get_pos_swipe(db: Session, swipe_id: int) -> Optional[PosSwipe]:
    return db.query(PosSwipe).filter(PosSwipe.id == swipe_id).first()

def update_pos_swipe(db: Session, swipe_id: int, data: schemas.PosSwipeUpdate, recalc_fee: bool = False) -> Optional[PosSwipe]:
    obj = db.query(PosSwipe).filter(PosSwipe.id == swipe_id).first()
    if not obj:
        return None
    old_card_id = obj.card_id
    old_amount = obj.amount
    updates = data.model_dump(exclude_unset=True)
    for key, val in updates.items():
        setattr(obj, key, val)
    db.flush()

    new_card_id = updates.get("card_id", old_card_id)
    new_amount = updates.get("amount", old_amount)

    # 如果金额或费率变化，重新计算手续费
    if recalc_fee:
        from app.finance.calc_engine import calc_pos_fee
        obj.fee = calc_pos_fee(new_amount, obj.fee_rate)

    # 处理信用卡额度变更
    def adjust_card(card_id, delta):
        if card_id:
            card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
            if card:
                card.current_balance = round((card.current_balance or 0) + delta, 2)

    if old_card_id == new_card_id:
        # 同一张卡，金额变化
        if old_amount != new_amount:
            adjust_card(old_card_id, new_amount - old_amount)
    else:
        # 换了卡：旧卡减掉原来的金额，新卡加上新金额
        adjust_card(old_card_id, -old_amount)
        adjust_card(new_card_id, new_amount)

    db.commit()
    db.refresh(obj)
    return obj

def delete_pos_swipe(db: Session, swipe_id: int) -> bool:
    swipe = db.query(PosSwipe).filter(PosSwipe.id == swipe_id).first()
    if not swipe:
        return False
    # 释放关联信用卡的已用额度
    if swipe.card_id:
        card = db.query(CreditCard).filter(CreditCard.id == swipe.card_id).first()
        if card:
            card.current_balance = round(max(0, (card.current_balance or 0) - swipe.amount), 2)
    _save_deleted_record(db, "pos_swipes", swipe.id, _serialize_record(swipe))
    db.delete(swipe)
    db.commit()
    return True


# --- CreditCard ---
def create_credit_card(db: Session, data: schemas.CreditCardCreate) -> CreditCard:
    card = CreditCard(**data.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card

def get_credit_cards(db: Session, person_id: Optional[int] = None) -> list[CreditCard]:
    q = db.query(CreditCard)
    if person_id:
        q = q.filter(CreditCard.person_id == person_id)
    return q.all()

def get_credit_card(db: Session, card_id: int) -> Optional[CreditCard]:
    return db.query(CreditCard).filter(CreditCard.id == card_id).first()

def update_credit_card(db: Session, card_id: int, data: schemas.CreditCardUpdate) -> Optional[CreditCard]:
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if card:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(card, key, val)
        db.commit()
        db.refresh(card)
    return card

def delete_credit_card(db: Session, card_id: int) -> bool:
    card = db.query(CreditCard).filter(CreditCard.id == card_id).first()
    if not card:
        return False
    _save_deleted_record(db, "credit_cards", card.id, _serialize_record(card))
    db.delete(card)
    db.commit()
    return True


# --- CreditCardTransaction ---
def create_card_transaction(db: Session, data: schemas.CreditCardTransactionCreate) -> CreditCardTransaction:
    txn = CreditCardTransaction(**data.model_dump())
    db.add(txn)
    card = db.query(CreditCard).filter(CreditCard.id == data.card_id).first()
    if card:
        if data.trans_type == "还款":
            card.current_balance = max(0, card.current_balance - data.amount)
        else:
            card.current_balance += data.amount
    db.commit()
    db.refresh(txn)
    return txn

def get_card_transactions(db: Session, card_id: Optional[int] = None,
                          person_id: Optional[int] = None) -> list[CreditCardTransaction]:
    q = db.query(CreditCardTransaction)
    if card_id:
        q = q.filter(CreditCardTransaction.card_id == card_id)
    if person_id:
        q = q.filter(CreditCardTransaction.person_id == person_id)
    return q.order_by(CreditCardTransaction.trans_date.desc()).all()

def get_card_transaction(db: Session, txn_id: int) -> Optional[CreditCardTransaction]:
    return db.query(CreditCardTransaction).filter(CreditCardTransaction.id == txn_id).first()

def update_card_transaction(db: Session, txn_id: int, data: schemas.CreditCardTransactionUpdate) -> Optional[CreditCardTransaction]:
    obj = db.query(CreditCardTransaction).filter(CreditCardTransaction.id == txn_id).first()
    if obj:
        old_amount = obj.amount
        old_type = obj.trans_type
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, val)
        # Adjust card balance based on changes
        card = db.query(CreditCard).filter(CreditCard.id == obj.card_id).first()
        if card:
            # Reverse old effect
            if old_type == "还款":
                card.current_balance += old_amount
            else:
                card.current_balance = max(0, card.current_balance - old_amount)
            # Apply new effect
            if obj.trans_type == "还款":
                card.current_balance = max(0, card.current_balance - obj.amount)
            else:
                card.current_balance += obj.amount
        db.commit()
        db.refresh(obj)
    return obj

def delete_card_transaction(db: Session, txn_id: int) -> bool:
    txn = db.query(CreditCardTransaction).filter(CreditCardTransaction.id == txn_id).first()
    if not txn:
        return False
    # Reverse balance effect before deleting
    card = db.query(CreditCard).filter(CreditCard.id == txn.card_id).first()
    if card:
        if txn.trans_type == "还款":
            card.current_balance += txn.amount
        else:
            card.current_balance = max(0, card.current_balance - txn.amount)
    _save_deleted_record(db, "credit_card_transactions", txn.id, _serialize_record(txn))
    db.delete(txn)
    db.commit()
    return True


# --- CardInstallment ---
def create_card_installment(db: Session, data: schemas.CardInstallmentCreate,
                            calc_fields: dict) -> CardInstallment:
    fields = data.model_dump(exclude={"rate_type", "rate_value"})
    inst = CardInstallment(**fields, **calc_fields)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst

def get_card_installments(db: Session, card_id: Optional[int] = None,
                          person_id: Optional[int] = None) -> list[CardInstallment]:
    q = db.query(CardInstallment)
    if card_id:
        q = q.filter(CardInstallment.card_id == card_id)
    if person_id:
        q = q.filter(CardInstallment.person_id == person_id)
    return q.order_by(CardInstallment.created_at.desc()).all()

def get_card_installment(db: Session, inst_id: int) -> Optional[CardInstallment]:
    return db.query(CardInstallment).filter(CardInstallment.id == inst_id).first()

def update_card_installment(db: Session, inst_id: int, data: schemas.CardInstallmentUpdate) -> Optional[CardInstallment]:
    obj = db.query(CardInstallment).filter(CardInstallment.id == inst_id).first()
    if obj:
        update_data = data.model_dump(exclude_unset=True)
        new_amount = update_data.get("amount", obj.amount)
        new_periods = update_data.get("periods", obj.periods)

        # 已还期数不能超过总期数
        if "paid_periods" in update_data:
            update_data["paid_periods"] = min(update_data["paid_periods"], new_periods)
        if "periods" in update_data and obj.paid_periods > new_periods:
            update_data["paid_periods"] = new_periods

        # 如果金额或期数变了，基于现有 period_rate 重新计算相关字段
        if "amount" in update_data or "periods" in update_data:
            period_rate = obj.period_rate
            update_data["period_principal"] = round(new_amount / new_periods, 2)
            update_data["period_fee"] = round(new_amount * period_rate, 2)
            update_data["total_fee"] = round(new_amount * period_rate * new_periods, 2)
            update_data["annual_rate"] = round(calc_installment_annual_rate(period_rate, new_periods), 4)
            update_data["period_total"] = round(update_data["period_principal"] + update_data["period_fee"], 2)

        for key, val in update_data.items():
            setattr(obj, key, val)
        db.commit()
        db.refresh(obj)
    return obj

def pay_installment_period(db: Session, inst_id: int) -> Optional[CardInstallment]:
    inst = db.query(CardInstallment).filter(CardInstallment.id == inst_id).first()
    if inst and inst.paid_periods < inst.periods:
        inst.paid_periods += 1
        # Add this period's payment to the card's current balance
        card = db.query(CreditCard).filter(CreditCard.id == inst.card_id).first()
        if card:
            card.current_balance += inst.period_total
        db.commit()
        db.refresh(inst)
    return inst

def delete_card_installment(db: Session, inst_id: int) -> bool:
    inst = db.query(CardInstallment).filter(CardInstallment.id == inst_id).first()
    if not inst:
        return False
    _save_deleted_record(db, "card_installments", inst.id, _serialize_record(inst))
    db.delete(inst)
    db.commit()
    return True


# --- Mortgage ---
def create_mortgage(db: Session, data: schemas.MortgageCreate) -> Mortgage:
    m = Mortgage(**data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

def get_mortgages(db: Session, person_id: Optional[int] = None) -> list[Mortgage]:
    q = db.query(Mortgage)
    if person_id:
        q = q.filter(Mortgage.person_id == person_id)
    return q.all()

def get_mortgage(db: Session, mortgage_id: int) -> Optional[Mortgage]:
    return db.query(Mortgage).filter(Mortgage.id == mortgage_id).first()

def update_mortgage(db: Session, mortgage_id: int, data: schemas.MortgageUpdate) -> Optional[Mortgage]:
    obj = db.query(Mortgage).filter(Mortgage.id == mortgage_id).first()
    if obj:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, val)
        db.commit()
        db.refresh(obj)
    return obj

def update_mortgage_principal(db: Session, mortgage_id: int, remaining_principal: float) -> Optional[Mortgage]:
    m = db.query(Mortgage).filter(Mortgage.id == mortgage_id).first()
    if m:
        m.remaining_principal = remaining_principal
        db.commit()
        db.refresh(m)
    return m

def delete_mortgage(db: Session, mortgage_id: int) -> bool:
    m = db.query(Mortgage).filter(Mortgage.id == mortgage_id).first()
    if not m:
        return False
    _save_deleted_record(db, "mortgages", m.id, _serialize_record(m))
    db.delete(m)
    db.commit()
    return True


# --- Income ---
def create_income(db: Session, data: schemas.IncomeCreate) -> Income:
    inc = Income(**data.model_dump())
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc

def get_incomes(db: Session, person_id: Optional[int] = None,
                period_value: Optional[str] = None) -> list[Income]:
    q = db.query(Income)
    if person_id:
        q = q.filter(Income.person_id == person_id)
    if period_value:
        q = q.filter(Income.period_value == period_value)
    return q.order_by(Income.created_at.desc()).all()

def get_income(db: Session, income_id: int) -> Optional[Income]:
    return db.query(Income).filter(Income.id == income_id).first()

def update_income(db: Session, income_id: int, data: schemas.IncomeUpdate) -> Optional[Income]:
    obj = db.query(Income).filter(Income.id == income_id).first()
    if obj:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, val)
        db.commit()
        db.refresh(obj)
    return obj

def delete_income(db: Session, income_id: int) -> bool:
    inc = db.query(Income).filter(Income.id == income_id).first()
    if not inc:
        return False
    _save_deleted_record(db, "incomes", inc.id, _serialize_record(inc))
    db.delete(inc)
    db.commit()
    return True


# --- Expense ---
def create_expense(db: Session, data: schemas.ExpenseCreate) -> Expense:
    exp = Expense(**data.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp

def get_expenses(db: Session, person_id: Optional[int] = None,
                 period_value: Optional[str] = None,
                 category: Optional[str] = None) -> list[Expense]:
    q = db.query(Expense)
    if person_id:
        q = q.filter(Expense.person_id == person_id)
    if period_value:
        q = q.filter(Expense.period_value == period_value)
    if category:
        q = q.filter(Expense.category == category)
    return q.order_by(Expense.expense_date.desc()).all()

def get_expense(db: Session, expense_id: int) -> Optional[Expense]:
    return db.query(Expense).filter(Expense.id == expense_id).first()

def update_expense(db: Session, expense_id: int, data: schemas.ExpenseUpdate) -> Optional[Expense]:
    obj = db.query(Expense).filter(Expense.id == expense_id).first()
    if obj:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, val)
        db.commit()
        db.refresh(obj)
    return obj

def delete_expense(db: Session, expense_id: int) -> bool:
    exp = db.query(Expense).filter(Expense.id == expense_id).first()
    if not exp:
        return False
    _save_deleted_record(db, "expenses", exp.id, _serialize_record(exp))
    db.delete(exp)
    db.commit()
    return True


# --- FeeConfig ---
def create_fee_config(db: Session, data: schemas.FeeConfigCreate) -> FeeConfig:
    fc = FeeConfig(**data.model_dump())
    db.add(fc)
    db.commit()
    db.refresh(fc)
    return fc

def get_fee_configs(db: Session) -> list[FeeConfig]:
    return db.query(FeeConfig).all()

def get_fee_config(db: Session, config_id: int) -> Optional[FeeConfig]:
    return db.query(FeeConfig).filter(FeeConfig.id == config_id).first()

def get_active_fee_config(db: Session, fee_type: str) -> Optional[FeeConfig]:
    return db.query(FeeConfig).filter(
        FeeConfig.fee_type == fee_type, FeeConfig.is_active == True
    ).first()

def update_fee_config(db: Session, config_id: int, data: schemas.FeeConfigCreate) -> Optional[FeeConfig]:
    fc = db.query(FeeConfig).filter(FeeConfig.id == config_id).first()
    if fc:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(fc, key, val)
        db.commit()
        db.refresh(fc)
    return fc

def delete_fee_config(db: Session, config_id: int) -> bool:
    fc = db.query(FeeConfig).filter(FeeConfig.id == config_id).first()
    if not fc:
        return False
    _save_deleted_record(db, "fee_configs", fc.id, _serialize_record(fc))
    db.delete(fc)
    db.commit()
    return True


# --- DebtSnapshot ---
def get_latest_snapshot(db: Session) -> Optional[DebtSnapshot]:
    return db.query(DebtSnapshot).order_by(DebtSnapshot.snapshot_date.desc()).first()

def get_today_snapshot(db: Session, today: date) -> Optional[DebtSnapshot]:
    return db.query(DebtSnapshot).filter(DebtSnapshot.snapshot_date == today).first()

def create_snapshot(db: Session, data: dict) -> DebtSnapshot:
    snap = DebtSnapshot(**data)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap

def get_snapshots(db: Session, months: int = 12) -> list[DebtSnapshot]:
    from datetime import timedelta
    cutoff = datetime.utcnow().date() - timedelta(days=months * 30)
    return db.query(DebtSnapshot).filter(
        DebtSnapshot.snapshot_date >= cutoff
    ).order_by(DebtSnapshot.snapshot_date).all()


# --- Recycle Bin helpers ---
import json

def _serialize_record(obj) -> str:
    """将 ORM 对象序列化为 JSON 字符串，处理 date/datetime 类型。"""
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        elif val is not None and not isinstance(val, (int, float, str, bool, type(None))):
            val = str(val)
        data[col.name] = val
    return json.dumps(data, ensure_ascii=False)


def _save_deleted_record(db: Session, table_name: str, record_id: int, record_data: str):
    """保存被删除的记录到回收站。"""
    dr = DeletedRecord(table_name=table_name, record_id=record_id, record_data=record_data)
    db.add(dr)


def get_deleted_records(db: Session) -> list[DeletedRecord]:
    return db.query(DeletedRecord).order_by(DeletedRecord.deleted_at.desc()).all()


def restore_record(db: Session, deleted_id: int) -> Optional[DeletedRecord]:
    """从回收站恢复记录。返回恢复后的 DeletedRecord 或 None。"""
    dr = db.query(DeletedRecord).filter(DeletedRecord.id == deleted_id).first()
    if not dr:
        return None
    record_data = json.loads(dr.record_data)
    table_name = dr.table_name
    # Map table name to model class
    model_map = {
        "persons": Person, "loan_platforms": LoanPlatform, "loans": Loan,
        "pos_swipes": PosSwipe, "credit_cards": CreditCard,
        "credit_card_transactions": CreditCardTransaction,
        "card_installments": CardInstallment, "mortgages": Mortgage,
        "incomes": Income, "expenses": Expense, "fee_configs": FeeConfig,
    }
    model_cls = model_map.get(table_name)
    if not model_cls:
        return None
    # Convert date strings back to date objects
    from datetime import date as date_type, datetime as datetime_type
    for key, val in record_data.items():
        if val and isinstance(val, str) and len(val) >= 10:
            try:
                if 'T' in val:
                    record_data[key] = datetime_type.fromisoformat(val)
                elif len(val) == 10:
                    record_data[key] = date_type.fromisoformat(val)
            except (ValueError, TypeError):
                pass
    # Remove id to let DB auto-increment
    record_data.pop("id", None)
    obj = model_cls(**record_data)
    db.add(obj)
    db.delete(dr)
    db.commit()
    return dr


def permanently_delete_record(db: Session, deleted_id: int) -> bool:
    dr = db.query(DeletedRecord).filter(DeletedRecord.id == deleted_id).first()
    if not dr:
        return False
    db.delete(dr)
    db.commit()
    return True


def clear_deleted_records(db: Session) -> int:
    count = db.query(DeletedRecord).count()
    db.query(DeletedRecord).delete()
    db.commit()
    return count


def clear_all_finance_data(db: Session) -> dict[str, int]:
    """清空所有财务相关数据（包括人员），返回各表删除行数。"""
    counts = {}
    # 先删子表（有外键依赖），再删主表
    for model_cls in [RepaymentPlan, CardInstallment, CreditCardTransaction,
                      PosSwipe, Loan, Mortgage, CreditCard,
                      Income, Expense, FeeConfig, DebtSnapshot, LoanPlatform, Person]:
        name = model_cls.__tablename__
        cnt = db.query(model_cls).delete()
        counts[name] = cnt
    db.commit()
    return counts
