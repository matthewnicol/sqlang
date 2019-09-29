# int = exactly this number of arguments
# tuple = between n1 and n2 args, accept as numbered params
#  empty list = accept any number of arguments, accept as 1 tuple/list
import datetime


def select_expr(eval, cols, frm, js, where, group, order):
    q = f"SELECT {', '.join([eval(c) for c in cols]) if isinstance(cols, list) or isinstance(cols, tuple) else eval(cols)} FROM {eval(frm)} "
    if js:
        q = f"{q} {eval(js)} "
    if where:
        q = f"{q} {eval(where)} "
    if group:
        q = f"{q} {eval(group)} "
    if order:
        q = f"{q} {eval(order)} "
    return q

elements = {
    'TABLE': (1, lambda r, out: out),
    'FIELD': (1, lambda r, out: out),
    'ALIAS': (2, lambda r, out1, out2: f"({r(out1)}) AS {out2} "),
    'SELECT': (6, select_expr),
    'JOINS': (("*",), lambda r, *js: " ".join([f"{r(j)} " for j in js])),
    'JOIN': (2, lambda r, ref, cond: f"INNER JOIN {r(ref)} ON {r(cond)} "),
    'WHERE': (1, lambda r, out: f"WHERE {r(out)} "),
    'EQ': (2, lambda r, expr1, expr2: f"{r(expr1)} = {r(expr2)} "),
    'GT': (2, lambda r, expr1, expr2: f"{r(expr1)} > {r(expr2)} "),
    'LT': (2, lambda r, expr1, expr2: f"{r(expr1)} < {r(expr2)} "),
    'LIKE': (2, lambda r, expr1, expr2: f"{r(expr1)} LIKE {r(expr2)} "),
    'AND': (("*",), lambda r, *args: f" ( {' AND '.join([r(a) for a in args])}) "),
    'OR': (("*",), lambda r, *args: f" ( {' OR '.join([r(a) for a in args])}) "),
    'NOT': (1, lambda r, expr: f"NOT ( {r(expr)})"),
    'ORDER_BY': ((1, 2), lambda r, *args: f"ORDER BY {r(args[0])} {args[1] if len(args) > 1 and args[1] else ''}"),
    'COUNT': (1, lambda r, a: f"COUNT({r(a)})"),
}


def element_count(element):
    return elements[element][0]

def substitution_rule(element):
    return elements[element][1]

def is_positional_args(element):
    return isinstance(element_count(element), int) or isinstance(element_count(element), tuple)

def matches_rule(item):
    return isinstance(item, Token) and item.key in [k for k in elements]


def cls_mth_maker(key):
    if isinstance(element_count(key), int):
        if element_count(key) == 0:
            @classmethod
            def cm(cls):
                assert(len(args) == 0)
                return Token(key.upper(), None)
        else:
            @classmethod
            def cm(cls, *args):
                assert len(args) == element_count(key)
                return Token(key.upper(), *args)
    elif isinstance(element_count(key), list):
        def cm(cls, args):
            return Token(key.upper(), args[0])
    # if tuple, elements passed as numbered params
    elif isinstance(element_count(key), tuple):
        @classmethod
        def cm(cls, *args):
            assert len(element_count(key)) == 0 \
                   or ((element_count(key)[0] == "*" or len(args) >= element_count(key)[0])
                       and element_count(key)[-1] == "*" or len(args) <= element_count(key)[-1])
            return Token(key.upper(), *args)
    else:
        raise ValueError(f'Unexpected input for element_count(key), key={key}')
    return cm

class Token:
    def __init__(self, key, *args):
        self.key = key
        self.elements = args

    def __repr__(self):
        return str((self.key, self.elements))

def sql_maker():
    class SQL:

        @classmethod
        def tokenize(cls, item):
            if isinstance(item, str):
                return f'"{item}"'
            elif isinstance(item, int):
                return f'{item}'
            elif isinstance(item, datetime.datetime):
                return f"'{item.year}-{item.month}-{item.day} {item.hours}:{item.minutes}:{item.seconds}'"
            elif isinstance(item, datetime.date):
                return f"'{item.year}-{item.month}-{item.day}'"
            else:
                return item


        @classmethod
        def eval(cls, item):
            if isinstance(item, tuple) and not matches_rule(item) and len(item) > 2 and matches_rule(item[1]):
                item = item[1]
            if matches_rule(item):
                key, item = item.key, item.elements
                if item == None:
                    return substitution_rule(key)(SQL.eval)
                if is_positional_args(key):
                    return substitution_rule(key)(SQL.eval, *item)
                else:
                    return substitution_rule(key)(SQL.eval, item)
            return SQL.tokenize(item)

        def __call__(self, item):
            return SQL.eval(item)

    for x in elements:
        setattr(SQL, x, cls_mth_maker(x))
    return SQL

SQL = sql_maker()

