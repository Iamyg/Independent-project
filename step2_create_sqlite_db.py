"""
第2步：创建TPC-H SQLite数据库
最终工作版 - 基于实际文件格式
"""

import sqlite3
import pandas as pd
import os
from pathlib import Path


class TPCHSQLiteBuilder:
    """
    TPC-H SQLite数据库构建器
    基于实际文件格式（每行末尾有|导致多一个空字段）
    """

    def __init__(self, db_path: str = "tpch.db"):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        print(f"✅ 连接到数据库: {self.db_path}")

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            print("✅ 数据库连接已关闭")

    def create_tables(self):
        """创建TPC-H的8张表"""
        cursor = self.conn.cursor()

        print("\n📦 创建TPC-H表结构...")

        # 先删除已有的表（避免冲突）
        tables_to_drop = ['lineitem', 'orders', 'partsupp', 'customer', 'supplier', 'part', 'nation', 'region']
        for table in tables_to_drop:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")

        # NATION表
        cursor.execute("""
        CREATE TABLE nation (
            n_nationkey INTEGER PRIMARY KEY,
            n_name TEXT NOT NULL,
            n_regionkey INTEGER NOT NULL,
            n_comment TEXT
        )
        """)
        print("  ✅ NATION表创建成功")

        # REGION表
        cursor.execute("""
        CREATE TABLE region (
            r_regionkey INTEGER PRIMARY KEY,
            r_name TEXT NOT NULL,
            r_comment TEXT
        )
        """)
        print("  ✅ REGION表创建成功")

        # PART表
        cursor.execute("""
        CREATE TABLE part (
            p_partkey INTEGER PRIMARY KEY,
            p_name TEXT NOT NULL,
            p_mfgr TEXT NOT NULL,
            p_brand TEXT NOT NULL,
            p_type TEXT NOT NULL,
            p_size INTEGER NOT NULL,
            p_container TEXT NOT NULL,
            p_retailprice DECIMAL(15,2) NOT NULL,
            p_comment TEXT
        )
        """)
        print("  ✅ PART表创建成功")

        # SUPPLIER表
        cursor.execute("""
        CREATE TABLE supplier (
            s_suppkey INTEGER PRIMARY KEY,
            s_name TEXT NOT NULL,
            s_address TEXT NOT NULL,
            s_nationkey INTEGER NOT NULL,
            s_phone TEXT NOT NULL,
            s_acctbal DECIMAL(15,2) NOT NULL,
            s_comment TEXT,
            FOREIGN KEY (s_nationkey) REFERENCES nation(n_nationkey)
        )
        """)
        print("  ✅ SUPPLIER表创建成功")

        # PARTSUPP表
        cursor.execute("""
        CREATE TABLE partsupp (
            ps_partkey INTEGER NOT NULL,
            ps_suppkey INTEGER NOT NULL,
            ps_availqty INTEGER NOT NULL,
            ps_supplycost DECIMAL(15,2) NOT NULL,
            ps_comment TEXT,
            PRIMARY KEY (ps_partkey, ps_suppkey),
            FOREIGN KEY (ps_partkey) REFERENCES part(p_partkey),
            FOREIGN KEY (ps_suppkey) REFERENCES supplier(s_suppkey)
        )
        """)
        print("  ✅ PARTSUPP表创建成功")

        # CUSTOMER表
        cursor.execute("""
        CREATE TABLE customer (
            c_custkey INTEGER PRIMARY KEY,
            c_name TEXT NOT NULL,
            c_address TEXT NOT NULL,
            c_nationkey INTEGER NOT NULL,
            c_phone TEXT NOT NULL,
            c_acctbal DECIMAL(15,2) NOT NULL,
            c_mktsegment TEXT NOT NULL,
            c_comment TEXT
        )
        """)
        print("  ✅ CUSTOMER表创建成功")

        # ORDERS表
        cursor.execute("""
        CREATE TABLE orders (
            o_orderkey INTEGER PRIMARY KEY,
            o_custkey INTEGER NOT NULL,
            o_orderstatus TEXT NOT NULL,
            o_totalprice DECIMAL(15,2) NOT NULL,
            o_orderdate DATE NOT NULL,
            o_orderpriority TEXT NOT NULL,
            o_clerk TEXT NOT NULL,
            o_shippriority INTEGER NOT NULL,
            o_comment TEXT,
            FOREIGN KEY (o_custkey) REFERENCES customer(c_custkey)
        )
        """)
        print("  ✅ ORDERS表创建成功")

        # LINEITEM表
        cursor.execute("""
        CREATE TABLE lineitem (
            l_orderkey INTEGER NOT NULL,
            l_partkey INTEGER NOT NULL,
            l_suppkey INTEGER NOT NULL,
            l_linenumber INTEGER NOT NULL,
            l_quantity DECIMAL(15,2) NOT NULL,
            l_extendedprice DECIMAL(15,2) NOT NULL,
            l_discount DECIMAL(15,2) NOT NULL,
            l_tax DECIMAL(15,2) NOT NULL,
            l_returnflag TEXT NOT NULL,
            l_linestatus TEXT NOT NULL,
            l_shipdate DATE NOT NULL,
            l_commitdate DATE NOT NULL,
            l_receiptdate DATE NOT NULL,
            l_shipinstruct TEXT NOT NULL,
            l_shipmode TEXT NOT NULL,
            l_comment TEXT,
            PRIMARY KEY (l_orderkey, l_linenumber),
            FOREIGN KEY (l_orderkey) REFERENCES orders(o_orderkey),
            FOREIGN KEY (l_partkey) REFERENCES part(p_partkey),
            FOREIGN KEY (l_suppkey) REFERENCES supplier(s_suppkey)
        )
        """)
        print("  ✅ LINEITEM表创建成功")

        self.conn.commit()
        print("\n✅ 所有表创建完成！")

    def import_table(self, table_name: str, tbl_file: str, expected_columns: int, column_names: list):
        """
        导入单个表的数据

        Args:
            table_name: 表名
            tbl_file: TBL文件路径
            expected_columns: 期望的列数
            column_names: 列名列表（长度必须等于expected_columns）
        """
        print(f"\n  📄 处理 {table_name}...")

        if not os.path.exists(tbl_file):
            print(f"    ⚠️ 文件不存在: {tbl_file}")
            return False

        try:
            # 读取TBL文件（|分隔，无表头）
            # 关键修复：只取前expected_columns列，忽略末尾的空字段
            df = pd.read_csv(tbl_file,
                             sep='|',
                             header=None,
                             names=column_names + ['dummy'] if len(
                                 column_names) < expected_columns + 1 else column_names,
                             usecols=range(expected_columns),  # 只取前expected_columns列
                             encoding='utf-8',
                             engine='python')

            print(f"    读取 {len(df)} 行，{len(df.columns)} 列")

            # 导入到SQLite
            df.to_sql(table_name, self.conn, if_exists='append', index=False)
            print(f"    ✅ 导入 {len(df)} 行")
            return True

        except Exception as e:
            print(f"    ❌ 导入失败: {e}")

            # 显示文件预览帮助调试
            try:
                with open(tbl_file, 'r', encoding='utf-8') as f:
                    print("    文件前2行预览:")
                    for i, line in enumerate(f):
                        if i >= 2:
                            break
                        parts = line.strip().split('|')
                        print(f"      行{i + 1}: {len(parts)}个字段")
                        for j, part in enumerate(parts[:5]):  # 只显示前5个
                            print(f"        字段{j + 1}: {repr(part[:50])}")
            except:
                pass

            return False

    def import_all_data(self, data_dir: str):
        """
        导入所有表的数据
        """
        print(f"\n📥 从 {data_dir} 导入TBL数据...")

        # 各表的列定义（基于实际文件格式）
        table_defs = {
            'nation': {
                'file': 'nation.tbl',
                'columns': 4,
                'names': ['n_nationkey', 'n_name', 'n_regionkey', 'n_comment']
            },
            'region': {
                'file': 'region.tbl',
                'columns': 3,
                'names': ['r_regionkey', 'r_name', 'r_comment']
            },
            'part': {
                'file': 'part.tbl',
                'columns': 9,
                'names': ['p_partkey', 'p_name', 'p_mfgr', 'p_brand', 'p_type',
                          'p_size', 'p_container', 'p_retailprice', 'p_comment']
            },
            'supplier': {
                'file': 'supplier.tbl',
                'columns': 7,
                'names': ['s_suppkey', 's_name', 's_address', 's_nationkey',
                          's_phone', 's_acctbal', 's_comment']
            },
            'partsupp': {
                'file': 'partsupp.tbl',
                'columns': 5,
                'names': ['ps_partkey', 'ps_suppkey', 'ps_availqty',
                          'ps_supplycost', 'ps_comment']
            },
            'customer': {
                'file': 'customer.tbl',
                'columns': 8,  # 实际文件有9个字段，但最后一个为空
                'names': ['c_custkey', 'c_name', 'c_address', 'c_nationkey',
                          'c_phone', 'c_acctbal', 'c_mktsegment', 'c_comment']
            },
            'orders': {
                'file': 'orders.tbl',
                'columns': 9,
                'names': ['o_orderkey', 'o_custkey', 'o_orderstatus', 'o_totalprice',
                          'o_orderdate', 'o_orderpriority', 'o_clerk', 'o_shippriority', 'o_comment']
            },
            'lineitem': {
                'file': 'lineitem.tbl',
                'columns': 16,
                'names': ['l_orderkey', 'l_partkey', 'l_suppkey', 'l_linenumber',
                          'l_quantity', 'l_extendedprice', 'l_discount', 'l_tax',
                          'l_returnflag', 'l_linestatus', 'l_shipdate', 'l_commitdate',
                          'l_receiptdate', 'l_shipinstruct', 'l_shipmode', 'l_comment']
            }
        }

        # 按依赖顺序导入
        import_order = ['nation', 'region', 'part', 'supplier', 'partsupp',
                        'customer', 'orders', 'lineitem']

        success_count = 0
        for table_name in import_order:
            table_def = table_defs[table_name]
            tbl_path = os.path.join(data_dir, table_def['file'])

            if self.import_table(table_name, tbl_path,
                                 table_def['columns'], table_def['names']):
                success_count += 1

        self.conn.commit()
        print(f"\n✅ 成功导入 {success_count}/8 张表")
        return success_count == 8

    def verify_data(self):
        """验证数据导入结果"""
        print("\n🔍 验证数据导入...")
        print("-" * 40)

        cursor = self.conn.cursor()

        tables = ['nation', 'region', 'part', 'supplier', 'partsupp', 'customer', 'orders', 'lineitem']
        total_rows = 0

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            total_rows += count
            print(f"  {table:10}: {count:8,} 行")

        print(f"\n  {'总计':10}: {total_rows:8,} 行")

        # 显示一些示例数据
        print("\n📋 示例数据 (每个表前1行):")
        for table in tables:
            cursor.execute(f"SELECT * FROM {table} LIMIT 1")
            row = cursor.fetchone()
            if row:
                print(f"\n  {table}:")
                for i, col in enumerate(cursor.description):
                    print(f"    {col[0]}: {row[i]}")

        cursor.close()


def main():
    """主函数"""
    print("=" * 60)
    print("第2步：创建TPC-H SQLite数据库（最终工作版）")
    print("=" * 60)

    # 配置
    DB_PATH = "tpch.db"
    DATA_DIR = "tpch_data"

    # 检查数据目录
    if not os.path.exists(DATA_DIR):
        print(f"\n❌ 数据目录不存在: {DATA_DIR}")
        print("请先运行第1步生成数据")
        return

    # 列出数据目录中的文件
    print(f"\n📁 数据目录: {DATA_DIR}")
    for file in sorted(os.listdir(DATA_DIR)):
        if file.endswith('.tbl'):
            size = os.path.getsize(os.path.join(DATA_DIR, file)) / 1024
            print(f"  📄 {file}: {size:.1f} KB")

    # 创建数据库构建器
    builder = TPCHSQLiteBuilder(DB_PATH)

    try:
        builder.connect()

        # 创建表结构
        builder.create_tables()

        # 导入数据
        if builder.import_all_data(DATA_DIR):
            # 验证数据
            builder.verify_data()

            # 获取数据库文件路径
            abs_path = os.path.abspath(DB_PATH)
            print("\n" + "=" * 60)
            print("✅ 第2步完成！")
            print("=" * 60)
            print(f"📁 数据库文件: {abs_path}")
            print(f"📊 数据库大小: {os.path.getsize(DB_PATH) / (1024 * 1024):.2f} MB")

        else:
            print("\n❌ 数据导入失败，请检查文件格式")

    finally:
        builder.close()


if __name__ == "__main__":
    main()