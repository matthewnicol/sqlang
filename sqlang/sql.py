# int = exactly this number of arguments
# tuple = between n1 and n2 args, accept as numbered params
#  empty list = accept any number of arguments, accept as 1 tuple/list
import datetime

class Token:
    def __init__(self, key, *args):
        self.key = key
        self.elements = args

    def __repr__(self):
        return str((self.key, self.elements))

    def __mul__(self, other):
        return Token('MULTIPLY', self, other)

    def __add__(self, other):
        return Token('ADD', self, other)

class Table(Token):
    def __init__(self, *args):
        super().__init__('TABLE', args[1])

    def __getattr__(self, item):
        if hasattr(super(), item):
            return object.__getattribute__(self, item)
        else:
            return Token('FIELD', f"{self.elements[0]}.{item}")

class Alias(Token):
    def __init__(self, *args):
        super().__init__('ALIAS', args[1], args[2])

    def __getattr__(self, item):
        if hasattr(super(), item):
            return object.__getattribute__(self, item)
        else:
            return Token('FIELD', f"{self.elements[1]}.{item}")


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

def update_expr(eval, tbl, js, sets, where, group, order):
    """
    group and order not allowed in multiple tables, so if join is allowed then group and order are not allowed
    """
    q = f"UPDATE {eval(tbl)} "
    if js:
        q = f"{q} {eval(js)} "
    if sets:
        q = f"{q} SET {', '.join([eval(s) for s in sets])} "
    if where:
        q = f"{q} {eval(where)} "
    if group:
        q = f"{q} {eval(group)} "
    if order:
        q = f"{q} {eval(order)} "
    return q

elements = {
    'TABLE': (1, lambda r, out: out, Table),
    'FIELD': (1, lambda r, out: out, Token),
    'ALIAS': (2, lambda r, out1, out2: f"{r(out1)} AS {out2} ", Alias),
    'SELECT': (6, select_expr),
    'UPDATE': (6, update_expr),
    'JOINS': (("*",), lambda r, *js: " ".join([f"{r(j)} " for j in js])),
    'JOIN': (2, lambda r, ref, cond: f"INNER JOIN {r(ref)} ON {r(cond)} "),
    'LEFT_JOIN': (2, lambda r, ref, cond: f"LEFT JOIN {r(ref)} ON {r(cond)} "),
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
    'DATE_FORMAT': (2, lambda r, d, f: f"DATE_FORMAT({r(d)}, {r(f)})", Token),
    'SUBSTRING': ((2,3), lambda r, e, s, f=None: f"SUBSTRING({r(e)}, {r(s)}{(', ' + r(f)) if f else ''})", Token),
    'UPPER': (1, lambda r, e: f"UPPER({r(e)})", Token),
    'IF': (3, lambda r, c, y, n: f"IF({r(c)}, {r(y)}, {r(n)})", Token),
    'RAND': (0, lambda r: "RAND()", Token),
    'DESC': (0, lambda r: "DESC", Token),
    'MULTIPLY': (2, lambda r, a, b: f"{r(a)} * {r(b)}", Token),
    'ADD': (2, lambda r, a, b: f"{r(a)} + {r(b)}", Token),
    'ROUND': (1, lambda r, e: f"ROUND({r(e)})", Token),
    'CONCAT': (('*',), lambda r, *a: f"CONCAT({', '.join([r(e) for e in a])})", Token),
    'IN': (2, lambda r, a, b: f"{r(a)} IN ({', '.join([r(bb) for bb in b])})", Token),
    'NOT_NULL': (1, lambda r, e: f"{r(e)} IS NOT NULL", Token),
    'CHAR': (1, lambda r, e: f"CHAR({r(e)})", Token),
    'LENGTH': (1, lambda r, e: f"LENGTH({r(e)})", Token),
    'TRIM': (1, lambda r, e: f"TRIM({r(e)})", Token),

}


def element_count(element):
    return elements[element][0]

def substitution_rule(element):
    return elements[element][1]

def token_handler(element):
    if len(elements[element]) > 2:
        return elements[element][2]
    else:
        return Token

def is_positional_args(element):
    return isinstance(element_count(element), int) or isinstance(element_count(element), tuple)

def matches_rule(item):
    return hasattr(item, 'key') and token_handler(item.key) == item.__class__


def cls_mth_maker(key):
    h = token_handler(key)
    if isinstance(element_count(key), int):
        if element_count(key) == 0:
            @classmethod
            def cm(cls):
                return h(key.upper(), None)
        else:
            @classmethod
            def cm(cls, *args):
                assert len(args) == element_count(key), (key, len(args), element_count(key), args)
                return h(key.upper(), *args)
    elif isinstance(element_count(key), list):
        def cm(cls, args):
            return h(key.upper(), args[0])
    # if tuple, elements passed as numbered params
    elif isinstance(element_count(key), tuple):
        @classmethod
        def cm(cls, *args):
            assert len(element_count(key)) == 0 \
                   or ((element_count(key)[0] == "*" or len(args) >= element_count(key)[0])
                       and element_count(key)[-1] == "*" or len(args) <= element_count(key)[-1])
            return h(key.upper(), *args)
    else:
        raise ValueError(f'Unexpected input for element_count(key), key={key}')
    return cm


def sql_maker():
    class SQL:

        @classmethod
        def tokenize(cls, item):
            if item is None:
                return "NULL"
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
            if matches_rule(item):
                key, item = item.key, item.elements
                if element_count(key) == 0:
                    return substitution_rule(key)(cls.eval)
                if item is None:
                    return substitution_rule(key)(cls.eval)
                if is_positional_args(key):
                    return substitution_rule(key)(cls.eval, *item)
                else:
                    return substitution_rule(key)(cls.eval, item)
            return SQL.tokenize(item)

        def __call__(self, item):
            return SQL.eval(item)

    for x in elements:
        setattr(SQL, x, cls_mth_maker(x))
    return SQL

SQL = sql_maker()

