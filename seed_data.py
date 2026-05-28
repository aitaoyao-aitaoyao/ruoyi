"""
LightPress CMS 种子数据脚本。
直接在数据库中生成测试数据，用于本地测试练习。

用法:
    python seed_data.py           # 向默认的 app.db 中写入种子数据
    python seed_data.py --reset   # 先删除所有表再重建，然后写入种子数据
"""
import argparse
from datetime import datetime, timedelta
from random import choice, randint

from app.db import engine, SessionLocal, Base
from app.models import User, Article, Category, Tag, Role
from app.auth import hash_password

# 分类数据 — 中文分类名，用于文章归类
CATEGORIES = [
    "技术教程", "设计美学", "商业洞察", "摄影技巧", "生活随笔",
    "旅行日记", "美食分享", "健康养生",
]

# 标签数据 — 保留英文技术术语，因为这些是编程领域的通用关键词
TAGS = [
    "python", "javascript", "fastapi", "vue", "react",
    "sql", "docker", "testing", "api", "devops",
    "tutorial", "opinion", "news",
]

# 预置用户 — 包含不同角色的账号，方便测试权限系统
USERS = [
    {"username": "admin", "email": "admin@lightpress.com", "full_name": "系统管理员",
     "password": "admin123", "is_superuser": True, "role": "admin"},
    {"username": "editor_jane", "email": "jane@lightpress.com", "full_name": "简编辑",
     "password": "editor123", "role": "editor"},
    {"username": "author_bob", "email": "bob@lightpress.com", "full_name": "鲍勃",
     "password": "author123", "role": "author"},
    {"username": "author_alice", "email": "alice@lightpress.com", "full_name": "爱丽丝",
     "password": "author123", "role": "author"},
    {"username": "author_tom", "email": "tom@lightpress.com", "full_name": "汤姆",
     "password": "author123", "role": "author"},
]

# 文章模板 — 用 {} 占位符填充标签名，生成多样化的文章标题
# 每条模板包含 (标题模板, 文章状态)
ARTICLE_TEMPLATES = [
    ("{} 入门指南", "published"),
    ("{} 高级技巧详解", "published"),
    ("{} 最佳实践（2026 版）", "published"),
    ("我为什么喜欢 {}", "draft"),
    ("从零搭建 {} 项目", "draft"),
    ("{} 与其他方案对比评测", "pending"),
    ("{} 常见问题排查手册", "pending"),
    ("{} 的未来发展趋势", "archived"),
    ("{} 性能调优实战", "published"),
    ("{} 安全防护指南", "published"),
]


def seed(reset: bool = False):
    """
    执行种子数据写入。

    流程:
        1. 如果 --reset，先删除并重建所有表
        2. 检查是否已经写入过（通过 admin 用户判断）
        3. 依次创建角色 → 用户 → 分类 → 标签 → 文章
        4. 文章会自动关联分类、标签、作者
    """
    db = SessionLocal()

    if reset:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    # 幂等检查：如果 admin 用户已存在，说明已经写入过种子数据
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("数据库已有种子数据，跳过写入。如需重新写入请使用 --reset 参数。")
        db.close()
        return

    # 第一步：创建角色（RBAC 权限体系的基础）
    roles = {}
    for name, desc in [("admin", "系统管理员"), ("editor", "内容编辑"), ("author", "普通作者")]:
        role = Role(name=name, description=desc)
        db.add(role)
        db.flush()  # 立即刷新以获取数据库分配的 id
        roles[name] = role

    # 第二步：创建用户，并关联对应角色
    users = {}
    for u in USERS:
        user = User(
            username=u["username"],
            email=u["email"],
            full_name=u["full_name"],
            hashed_password=hash_password(u["password"]),  # 密码哈希存储，不存明文
            is_superuser=u.get("is_superuser", False),
            created_at=datetime.utcnow() - timedelta(days=randint(30, 365)),
        )
        if u["role"] in roles:
            user.roles.append(roles[u["role"]])
        db.add(user)
        db.flush()
        users[u["username"]] = user

    # 第三步：创建分类（slug 由名称自动生成）
    categories = {}
    for name in CATEGORIES:
        slug = name.lower().replace(" ", "-")
        cat = Category(name=name, slug=slug, description=f"关于 {name} 的文章合集")
        db.add(cat)
        db.flush()
        categories[name] = cat

    # 第四步：创建标签
    tags = {}
    for name in TAGS:
        tag = Tag(name=name, slug=name.lower().replace(" ", "-"))
        db.add(tag)
        db.flush()
        tags[name] = tag

    # 第五步：创建文章（最多 50 篇，覆盖不同状态和主题）
    authors = [users["author_bob"], users["author_alice"], users["author_tom"]]
    editor = users["editor_jane"]
    now = datetime.utcnow()

    article_count = 0
    for tag_name in TAGS:
        for tmpl_title, status in ARTICLE_TEMPLATES:
            if article_count >= 50:
                break
            title = tmpl_title.format(tag_name.title())
            author = choice(authors)

            article = Article(
                title=title,
                slug=title.lower().replace(" ", "-").replace(":", "").replace("'", ""),
                content=f"这是一篇关于 {tag_name} 的{status}文章。标题为「{title}」，"
                        f"内容涵盖了 {tag_name} 的核心知识点，并提供了实用的参考信息。",
                excerpt=f"关于 {tag_name} 的一篇{status}文章。",
                status=status,
                category_id=choice(list(categories.values())).id,
                author_id=author.id,
                created_at=now - timedelta(days=randint(1, 180)),
                updated_at=now - timedelta(hours=randint(1, 720)),
            )
            # 每篇文章至少关联当前标签
            article.tags.append(tags[tag_name])
            # 随机给部分文章追加第二个标签
            if randint(0, 1):
                extra_tag = choice([t for t in TAGS if t != tag_name])
                article.tags.append(tags[extra_tag])

            # 已发布/已归档的文章：设置发布时间 + 审核人
            if status in ("published", "archived"):
                article.published_at = now - timedelta(days=randint(1, 90))
                article.reviewed_by = editor.id

            db.add(article)
            article_count += 1

        if article_count >= 50:
            break

    db.commit()
    print(f"种子数据写入完成: {len(roles)} 个角色, {len(users)} 个用户, "
          f"{len(categories)} 个分类, {len(tags)} 个标签, "
          f"{article_count} 篇文章。")
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LightPress CMS 种子数据管理工具")
    parser.add_argument("--reset", action="store_true",
                        help="写入前先删除并重建所有表")
    args = parser.parse_args()
    seed(reset=args.reset)
