import datetime
from inspect import Signature

def create_token_list():
    return {}

def token_list(tset={}, *tokens):
    for t in tokens:
        k, v = list(t.items())[0]
        tset[k] = v
    return tset

def token_list_item(key, *evaluations):
    return {key: evaluations}

def evaluate_token(evaluate, tokens, key, args):
    for func in tokens[key]:
        res = func(evaluate, *args)
        if res:
            return res
    raise ValueError("No evaluators work")

def bind_token(attr, *args):
    return (f"TOKEN:{attr}", *args)

def token_key(obj):
    return token_key_part(obj).replace("TOKEN:", "")

def token_key_part(obj):
    return obj[0]

def token_arguments(obj):
    return obj[1:] if len(obj) > 1 else tuple()

def is_token(obj):
    return isinstance(obj, tuple) and len(obj) > 0 and token_key_part(obj).startswith("TOKEN:")

def is_string(obj):
    return str(obj)


def bound_token_maker(name):
    def func(*args):
        return bind_token(name, *args)
    return func

def BUILD_SQL(tokens):
    class S:
        def __getattr__(self, attr):
            if attr in tokens:
                return bound_token_maker(attr)
            raise AttributeError(f"Attribute {attr} doesn't exist on this {self}")

        def __call__(self, obj):
            return self.__class__.evaluate(obj)

        @classmethod
        def evaluate(cls, obj):
            if is_token(obj):
                return evaluate_token(cls.evaluate, tokens, token_key(obj), token_arguments(obj))
            else:
                return cls.serialize(obj)
        
        @classmethod
        def serialize(cls, item):
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

    sql = S()
    return sql

def evaluate_from(evaluate, *args):
    return 'FROM ' + (' '.join([evaluate(a) for a in args]))

def evaluate_select(evaluate, *args):
    if is_token(args[0]) and token_key(args[0]) == 'DISTINCT':
        offset = 1
        val = f"SELECT {evaluate(args[0])}"
    else:
        offset = 0
        val = f"SELECT"
    # fields/subqueries
    if is_token(args[0+offset]) and token_key(args[0+offset]) == 'FIELD':
        val = f"{val} {evaluate(args[0+offset])}"
    else:
        val = f"{val} {', '.join([evaluate(a) for a in args[0+offset]])}"
    offset += 1
    # from, group, order
    for arg in args[offset:]:
        val = " ".join([val] + [evaluate(arg)])
    return val

def evaluate_insert(evaluate, *args):
    val = f"INSERT INTO {evaluate(args[0])}"
    for a in args[1:]:
        val += " " + evaluate(a)
    return val
        

def evaluate_field(evaluate, *args):
    if len(args) == 1 and is_string(args[0]):
        return args[0]
    if len(args) == 2 and is_string(args[0]) and is_string(args[1]):
        return f"{args[0]} AS {args[1]}"
    if len(args) >= 2 and is_token(args[0]) and token_key(args[0]) in ('TABLE', 'SELECT'):
        # Table is not aliased.
        if len(token_arguments(args[0])) == 1:
            if token_key(args[0]) == 'SELECT':
                raise ValueError("Subquery passed to FIELD must be aliased")
            val = ".".join(token_arguments(args[0])[0], args[1])
            if len(args) == 3:
                return f"{val} AS {args[2]}"
            else:
                return val
        # Table is aliased.
        elif len(token_arguments(args[0])) == 2:
            val = ".".join(token_arguments(args[0])[1], args[1])
            if len(args) == 3:
                return f"{val} AS {args[2]}"
            else:
                return val
    raise ValueError('Error parsing')

tokens = token_list(
    create_token_list(),
    token_list_item(
        'TABLE', 
        lambda evaluate, *args: f"{args[0]}{' '.join([' AS', args[1]]) if len(args) == 2 else ''}"
    ),
    token_list_item('FROM', evaluate_from),
    token_list_item('SELECT', evaluate_select),
    token_list_item('INSERT', evaluate_insert),
    token_list_item('FIELD', evaluate_field),
    token_list_item('SET', lambda r, *args: f"SET " + (", ".join([r(a) for a in args]))),
    token_list_item('JOIN', lambda r, *args: f"INNER JOIN {r(args[0])} ON {r(args[1])} "),
    token_list_item('LEFT_JOIN', lambda r, *args: f"LEFT JOIN {r(args[0])} ON {r(args[1])} "),
    token_list_item('WHERE', lambda r, *args: f"WHERE {r(args[0])} "),
    token_list_item('EQ', lambda r, *args: f"{r(args[0])} = {r(args[1])}"),
    token_list_item('GT', lambda r, *args: f"{r(args[0])} > {r(args[1])}"),
    token_list_item('LT', lambda r, *args: f"{r(args[0])} < {r(args[1])}"),
    token_list_item('LIKE', lambda r, *args: f"{r(args[0])} LIKE {r(args[1])} "),
    token_list_item('AND', lambda r, *args: f" ( {' AND '.join([r(a) for a in args])})"),
    token_list_item('OR',  lambda r, *args: f" ( {' OR '.join([r(a) for a in args])})"),
    token_list_item('NOT', lambda r, *args: f"NOT ( {r(args[0])})"),
    token_list_item('ORDER_BY', lambda r, *args: f"ORDER BY {r(args[0])} {r(args[1]) if len(args) > 1 and args[1] else ''}"),
    token_list_item('COUNT', lambda r, *args: f"COUNT({r(args[0])}{(' '+r(args[1])) if token_key(args[0]) == 'DISTINCT' else ''})"),
    token_list_item('DATE_FORMAT', lambda r, *args: f"DATE_FORMAT({r(args[0])}, {r(args[1])})"),
    token_list_item('SUBSTRING', lambda r, *args: f"SUBSTRING({r(args[0])}, {r(args[1])}{(', ' + r(args[2])) if len(args) > 2 else ''})"),
    token_list_item('UPPER', lambda r, *args: f"UPPER({r(args[0])})"),
    token_list_item('IF', lambda r, *args: f"IF({r(args[0])}, {r(args[1])}, {r(args[2])})"),
    token_list_item('RAND', lambda r, *args: "RAND()"),
    token_list_item('DESC', lambda r, *args: "DESC"),
    token_list_item('ASC', lambda r, *args: "ASC"),
    token_list_item('MULTIPLY', lambda r, *args: f' * '.join([r[a] for a in args])),
    token_list_item('ADD', lambda r, *args: f' + '.join([r[a] for a in args])),
    token_list_item('SUB', lambda r, *args: f' - '.join([r[a] for a in args])),
    token_list_item('ROUND', lambda r, *args: f"ROUND({r(args[0])})"),
    token_list_item('CONCAT', lambda r, *args: f"CONCAT({', '.join([r(e) for e in a])})"),
    token_list_item('IN', lambda r, *args: f"{r(args[0])} IN ({', '.join([r(bb) for bb in args[1]])})"),
    token_list_item('NOT_NULL', lambda r, *args: f"{r(args[0])} IS NOT NULL"),
    token_list_item('CHAR', lambda r, *args: f"CHAR({r(args[0])})"),
    token_list_item('LENGTH', lambda r, *args: f"LENGTH({r(args[0])})"),
    token_list_item('TRIM', lambda r, *args: f"TRIM({r(args[0])})"),
)

# Legacy Implementation
###################################

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


def validate_argument_count(element_count, args):
    if isinstance(element_count, int):
        return len(args) == element_count
    elif isinstance(element_count, tuple):
        return (element_count[0] == "*" or len(args) >= element_count[0]) and (element_count[-1] == "*" or len(args) <= element_count[-1])
    elif isinstance(element_count, list):
        return (element_count[0] == "*" or len(args) >= element_count[0]) and (element_count[-1] == "*" or len(args) <= element_count[-1])
    return False

class SQL:
    eval_funcs = {}
    element_counts = {}

    @classmethod
    def consume(cls, key, element_count, eval_func, token=Token):
        @classmethod
        def getter(cls, *args):
            if not validate_argument_count(element_count, args):
                raise Exception(f"Argument count wrong for {key}, {element_count}, {args}")
            if element_count == 0:
                return token(key.upper(), None)
            elif isinstance(element_count, list):
                return token(key.upper(), args[0])
            else:
                return token(key.upper(), *args)
        setattr(cls, key, getter)
        cls.eval_funcs[key] = eval_func
        cls.element_counts[key] = element_count

    @classmethod
    def serialize(cls, item):
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
        if hasattr(item, 'key') and item.key in cls.eval_funcs:
            key, item = item.key, item.elements
            if cls.element_counts[key] == 0:
                return cls.eval_funcs[key](cls.eval)
            if item is None:
                return cls.eval_funcs[key](cls.eval)
            if isinstance(cls.element_counts[key], tuple) or isinstance(cls.element_counts[key], int):
                return cls.eval_funcs[key](cls.eval, *item)
            else:
                return cls.eval_funcs[key](cls.eval, item)
        return SQL.serialize(item)

    def __call__(self, item):
        return SQL.eval(item)

elements = {
    'TABLE': (1, lambda r, out: out, Table),
    'FIELD': (1, lambda r, out: out),
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

for e in elements:
    SQL.consume(e, elements[e][0], elements[e][1], token=elements[e][2] if len(elements[e]) > 2 else Token)

