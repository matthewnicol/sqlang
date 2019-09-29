import unittest
from sqlang.sql import SQL
import pymysql
import datetime

class BasicSQLTester(unittest.TestCase):

    def setUp(self):
        self.con = pymysql.connect(host='localhost', user='root', db='nbabrain', password='')
        self.cur = self.con.cursor()

    def test_basic_select(self):
        s = SQL()
        expr = SQL.SELECT(
            SQL.FIELD('uid'),
            SQL.TABLE('meeting'),
            None, #joins
            SQL.WHERE(SQL.EQ(SQL.FIELD('home'), 'BOS')),
            None,
            None
        )
        print(s(expr))
        self.cur.execute(s(expr))


        expr = SQL.SELECT(
            [SQL.FIELD('team.name'), SQL.COUNT(SQL.FIELD('meeting.uid'))],
            SQL.TABLE('meeting'),
            SQL.JOINS(
                SQL.JOIN(
                    SQL.TABLE('team'), 
                    SQL.AND(
                        SQL.EQ(SQL.FIELD('meeting.home'), SQL.FIELD('team.name')), 
                        SQL.GT('game_date', datetime.date(2014, 5, 10))
                    )
                )
            ),
            SQL.WHERE(SQL.NOT(SQL.LIKE(SQL.FIELD('team.uid'), '%PHI%'))),
            None,
            SQL.ORDER_BY(SQL.FIELD('meeting.uid'), 'desc')
        )

        print(s(expr))
        self.cur.execute(s(expr))
