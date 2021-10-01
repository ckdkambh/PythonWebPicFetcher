from functools import wraps

def outermost(*args):
    def out(func):
        print ("装饰器参数{}".format(args))
        @wraps(func)
        def inner(*args):
            print("innet start")
            func(*args)
            print ("inner end")
        return inner
    return out

class Test():
    @outermost(666)
    def myfun(self, name):
        print ("试试装饰器和函数都带参数的情况,被装饰的函数参数{}".format(name))

obj = Test()
obj.myfun("zhangkun")
print(obj.myfun.__name__)