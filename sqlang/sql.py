import datetime

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

def bind_expression(attr, *args):
    return (f"EXPRESSION:{attr}", *args)

def token_key(obj):
    return token_key_part(obj).replace("TOKEN:", "")

def token_key_part(obj):
    return obj[0]

def token_arguments(obj):
    return obj[1:] if len(obj) > 1 else tuple()

def is_token(obj):
    return isinstance(obj, tuple) and len(obj) > 0 and token_key_part(obj).startswith("TOKEN:")

def is_string(obj):
    return isinstance(obj, str)

def bound_expression_maker(name):
    def func(*args):
        return bind_expression(name, *args)
    return func

def bound_token_maker(name):
    def func(*args):
        return bind_token(name, *args)
    return func

def SQL(tokens):
    class S:
        def __getattr__(self, attr):
            if attr in tokens:
                return bound_token_maker(attr)
            raise AttributeError(f"Attribute {attr} doesn't exist on this {self}")

        def __call__(self, obj):
            return self.__class__.evaluate(obj, self)

        @classmethod
        def evaluate(cls, obj, inst=None):
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
    if is_token(args[0]) and token_key(args[0]) == 'IGNORE':
        val = "INSERT IGNORE INTO"
        offset = 1
    else:
        val = "INSERT INTO"
        offset = 0
    val = f"{val} {evaluate(args[offset])}"
    for a in args[offset+1:]:
        val += " " + evaluate(a)
    return val

def evaluate_update(evaluate, *args):
    val = f"UPDATE {evaluate(args[0])}"
    for a in args[1:]:
        val += " " + evaluate(a)
    return val


def evaluate_field(evaluate, *args):
    if len(args) == 1 and is_string(args[0]):
        return args[0]
    if len(args) >= 2 and is_token(args[0]) and token_key(args[0]) in ('TABLE', 'SELECT'):
        # Table is not aliased.
        if len(token_arguments(args[0])) == 1:
            if token_key(args[0]) == 'SELECT':
                raise ValueError("Subquery passed to FIELD must be aliased")
            val = ".".join([token_arguments(args[0])[0], args[1]])
            if len(args) == 3:
                return f"{val} AS {args[2]}"
            else:
                return val
        # Table is aliased.
        elif len(token_arguments(args[0])) == 2:
            val = ".".join([token_arguments(args[0])[1], args[1]])
            if len(args) == 3:
                return f"{val} AS {args[2]}"
            else:
                return val
    if len(args) == 2 and is_string(args[0]) and is_string(args[1]):
        return f"{args[0]} AS {args[1]}"
    raise ValueError('Error parsing')

tokens = token_list(
    create_token_list(),
    token_list_item(
        'TABLE', 
        lambda evaluate, *args: f"{args[0]}{' '.join([' AS', args[1]]) if len(args) == 2 else ''}"
    ),
    token_list_item('FROM', evaluate_from),
    token_list_item('SELECT', evaluate_select),
    token_list_item('UPDATE', evaluate_update),
    token_list_item('INSERT', evaluate_insert),
    token_list_item('FIELD', evaluate_field),
    token_list_item('SET', lambda r, *args: f"SET " + (", ".join([r(a) for a in args]))),
    token_list_item('VALUES', lambda r, *args: f"VALUES " + (", ".join([r(a) for a in args]))),
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
    token_list_item('IGNORE', lambda r, *args: "IGNORE"),
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
    token_list_item('GROUP_BY', lambda r, *args: f"GROUP BY {', '.join([r(a) for a in args])}"),
)
