"""
最终修复版 - 在dbgen目录下运行，然后移动文件到目标目录
"""

import subprocess
import os
import shutil
from pathlib import Path


class TPCHDataGenerator:
    """TPC-H数据生成器 - 最终修复版"""

    def __init__(self, dbgen_path: str, scale_factor: float = 0.01):
        self.dbgen_path = Path(dbgen_path)
        self.dbgen_dir = self.dbgen_path.parent
        self.scale_factor = scale_factor

        if not self.dbgen_path.exists():
            raise FileNotFoundError(f"dbgen.exe not found at: {dbgen_path}")

        # 检查dists.dss
        self.dists_path = self.dbgen_dir / "dists.dss"
        if not self.dists_path.exists():
            raise FileNotFoundError(f"dists.dss not found at: {self.dists_path}")

    def generate_data(self, output_dir: str = "tpch_data"):
        """
        生成TPC-H数据

        关键修复：在dbgen目录下运行，然后移动文件
        """

        print("=" * 60)
        print(f"TPC-H数据生成器 v3.0.1 (最终修复版)")
        print("=" * 60)
        print(f"dbgen路径: {self.dbgen_path}")
        print(f"dbgen目录: {self.dbgen_dir}")
        print(f"dists.dss: {self.dists_path}")
        print(f"规模因子: {self.scale_factor}")
        print(f"输出目录: {output_dir}")

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 保存当前目录
        original_dir = os.getcwd()

        try:
            # 切换到dbgen目录（关键修复！）
            print(f"\n📂 切换到dbgen目录: {self.dbgen_dir}")
            os.chdir(self.dbgen_dir)

            # 构建命令（现在在当前目录运行，可以找到dists.dss）
            cmd = [
                str(self.dbgen_path),
                "-v",  # 详细输出
                "-f",  # 强制覆盖
                "-s", str(self.scale_factor),  # 规模因子
            ]

            print(f"\n📦 执行命令: {' '.join(cmd)}")
            print("正在生成数据，请稍候...")

            # 执行dbgen
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print("❌ dbgen执行失败:")
                if result.stderr:
                    print(result.stderr)
                else:
                    print(result.stdout)
                return False

            print("✅ dbgen执行成功")

            # 需要移动的文件列表
            expected_files = [
                'customer.tbl',
                'lineitem.tbl',
                'nation.tbl',
                'orders.tbl',
                'part.tbl',
                'partsupp.tbl',
                'region.tbl',
                'supplier.tbl'
            ]

            print("\n📊 移动生成的文件:")
            moved_files = []
            for file in expected_files:
                src = Path(self.dbgen_dir) / file
                dst = Path(original_dir) / output_dir / file

                if src.exists():
                    # 移动文件到输出目录
                    shutil.move(str(src), str(dst))
                    size = dst.stat().st_size / (1024 * 1024)  # MB

                    # 统计行数
                    with open(dst, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = sum(1 for _ in f)

                    print(f"  ✅ {file:15} {size:8.2f} MB, {lines:10,} 行")
                    moved_files.append(file)
                else:
                    print(f"  ⚠️ {file:15} 未生成")

            print(f"\n📈 成功移动 {len(moved_files)} 个文件")

            # 清理可能生成的临时文件
            for ext in ['.sql', '.log']:
                for tmp_file in Path(self.dbgen_dir).glob(f"*{ext}"):
                    tmp_file.unlink()

            return True

        finally:
            # 恢复原目录
            os.chdir(original_dir)

    def convert_to_csv(self, data_dir: str):
        """
        将.tbl文件转换为CSV格式
        TPC-H使用'|'作为分隔符
        """
        print(f"\n📝 转换.tbl文件为CSV格式...")

        data_path = Path(data_dir)
        tbl_files = list(data_path.glob("*.tbl"))

        if not tbl_files:
            print("  ⚠️ 没有找到.tbl文件")
            return

        for tbl_file in tbl_files:
            csv_file = tbl_file.with_suffix('.csv')

            print(f"  处理 {tbl_file.name} -> {csv_file.name}")

            # 统计原始行数
            with open(tbl_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = sum(1 for _ in f)

            # 转换文件
            with open(tbl_file, 'r', encoding='utf-8', errors='ignore') as fin, \
                    open(csv_file, 'w', encoding='utf-8', newline='') as fout:

                for line in fin:
                    # 移除末尾的'|'和换行符
                    line = line.rstrip('\n').rstrip('|')
                    fout.write(line + '\n')

            print(f"    转换完成: {lines:,} 行")

        print("✅ CSV转换完成")


def main():
    """主函数"""

    # dbgen的完整路径
    DBGEN_PATH = r"D:\Code_Project\Python_Project\IP\TPC-H V3.0.1\dbgen\dbgen.exe"
    SCALE_FACTOR = 0.1  # 100MB测试数据
    OUTPUT_DIR = "tpch_data"

    try:
        # 创建数据生成器
        generator = TPCHDataGenerator(DBGEN_PATH, SCALE_FACTOR)

        # 生成数据
        if generator.generate_data(OUTPUT_DIR):
            # 转换为CSV
            generator.convert_to_csv(OUTPUT_DIR)

            print("\n" + "=" * 60)
            print("✅ 第1步完成！")
            print("=" * 60)
            print(f"数据位置: {os.path.abspath(OUTPUT_DIR)}")
            print("\n生成的文件:")
            for file in os.listdir(OUTPUT_DIR):
                if file.endswith('.csv'):
                    size = os.path.getsize(os.path.join(OUTPUT_DIR, file)) / 1024
                    print(f"  📄 {file}: {size:.1f} KB")

            print("\n下一步: 运行 step2_create_sqlite_db.py 创建数据库")

    except Exception as e:
        print(f"\n❌ 错误: {e}")


if __name__ == "__main__":
    main()