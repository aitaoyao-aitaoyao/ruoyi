"""
数据库配置模块 — 使用 SQLAlchemy 2.0 连接 SQLite

SQLite 是零配置的文件型数据库，数据存储在项目根目录的 app.db 文件中。
适合本地开发和测试练习，无需安装额外的数据库服务。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# 数据库连接 URL：使用项目根目录下的 app.db 文件
SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

# 创建数据库引擎
# connect_args={"check_same_thread": False} 是 SQLite 特有的配置，
# 允许 FastAPI 的多个请求线程共享同一个数据库连接（默认 SQLite 不允许跨线程）
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# 创建会话工厂
# autocommit=False: 需要手动 commit 才会写入数据库
# autoflush=False: 需要手动 flush 才会将变更同步到数据库
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# DeclarativeBase 是所有 ORM 模型的基类
# 所有模型类继承它后，SQLAlchemy 会自动将其映射为数据库表
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI 依赖注入函数：为每个请求创建一个独立的数据库会话。

    使用 generator（yield）模式：
    1. 请求进来时创建会话
    2. 将会话交给路由处理函数
    3. 请求结束后自动关闭会话，释放连接资源

    用法：
        @app.get("/users")
        def list_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
