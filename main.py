import functools

def log_decorator(func):
    @functools.wraps(func)  # 保留原函数信息
    def wrapper(*args, **kwargs):
        print(f"begin call {func.__name__}")
        result = func(*args, **kwargs)  # 执行原函数
        print(f"end call {func.__name__}")
        return result
    return wrapper

@log_decorator
def hello():
    print("hello world")

hello();