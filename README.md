# SQLANG
*Generate SQL with functional calls.*

Use base set of tokens:

```
from sqlang import SQL, tokens

S = SQL(tokens)

expr = S.SELECT([S.FIELD('id')], S.FROM(S.TABLE('example')))
print(S(expr))

 "SELECT id FROM example;"
```

Add your own expression tokens:

```
from sqlang.sql import SQL as SQL_
from sqlang.sql import token_list, token_list_item, tokens

t2 = token_list(
    tokens,
    token_list_item('REPLACE', lambda e, *args: f"REPLACE({e(args[0])}, {e(args[1])}, {e(args[2])})"),
    token_list_item('WHERE', lambda e, *args: f"WHERE {e(args[0])}"),
    token_list_item('NOT_LIKE', lambda e, *args: f"{e(args[0])} NOT LIKE {e(args[1])}"),
)

SQL = SQL_(t2)
```


