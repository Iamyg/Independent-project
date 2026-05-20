"""
R2T算法完整版 - 全表查询版本（无WHERE条件）
支持COUNT和SUM查询，包含多次试验统计
"""

import sqlite3
import numpy as np
import pulp
import math
from collections import defaultdict
import time


class R2TComplete:
    """完整版R2T算法 - 全表查询版本"""

    def __init__(self, db_path: str, epsilon: float = 1.0):
        self.db_path = db_path
        self.epsilon = epsilon
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)

    def close(self):
        if self.conn:
            self.conn.close()

    def get_true_answer(self, sql: str) -> float:
        """获取真实结果"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql)
            result = cursor.fetchone()[0]
            return float(result) if result is not None else 0.0
        finally:
            cursor.close()

    def get_true_count(self) -> float:
        """真实COUNT结果 - 全表"""
        sql = """
            SELECT COUNT(*)
            FROM customer, orders, lineitem
            WHERE c_custkey = o_custkey AND o_orderkey = l_orderkey
        """
        return self.get_true_answer(sql)

    def get_true_sum(self) -> float:
        """真实SUM结果 - 全表"""
        sql = """
            SELECT SUM(l_extendedprice * (1 - l_discount))
            FROM customer, orders, lineitem
            WHERE c_custkey = o_custkey AND o_orderkey = l_orderkey
        """
        return self.get_true_answer(sql)

    def prepare_count_data(self):
        """准备COUNT查询数据 - 全表版本"""
        query = """
            SELECT 
                c.c_custkey,
                l.rowid
            FROM customer c
            JOIN orders o ON c.c_custkey = o.o_custkey
            JOIN lineitem l ON o.o_orderkey = l.l_orderkey
            ORDER BY c.c_custkey
        """

        cursor = self.conn.cursor()
        try:
            cursor.execute(query)

            psi_values = []  # COUNT查询每个权重为1
            primary_to_results = defaultdict(list)

            rows = cursor.fetchall()
            for idx, (custkey, _) in enumerate(rows):
                psi_values.append(1.0)
                primary_to_results[custkey].append(idx)

            c_j_sets = list(primary_to_results.values())

            return psi_values, c_j_sets
        finally:
            cursor.close()

    def prepare_sum_data(self):
        """准备SUM查询数据 - 全表版本"""
        query = """
            SELECT 
                c.c_custkey,
                l.l_extendedprice * (1 - l.l_discount) as amount
            FROM customer c
            JOIN orders o ON c.c_custkey = o.o_custkey
            JOIN lineitem l ON o.o_orderkey = l.l_orderkey
            ORDER BY c.c_custkey
        """

        cursor = self.conn.cursor()
        try:
            cursor.execute(query)

            psi_values = []
            primary_to_results = defaultdict(list)

            rows = cursor.fetchall()
            for idx, (custkey, amount) in enumerate(rows):
                psi_values.append(float(amount))
                primary_to_results[custkey].append(idx)

            c_j_sets = list(primary_to_results.values())

            return psi_values, c_j_sets
        finally:
            cursor.close()

    def compute_ds_q(self, c_j_sets, psi_values):
        """计算DS_Q（下向局部敏感度）"""
        if not c_j_sets:
            return 0
        return max(sum(psi_values[k] for k in c_j) for c_j in c_j_sets)

    def solve_lp(self, psi_values, c_j_sets, tau, time_limit=120):
        """求解LP：最大化sum(u_k)，约束每个客户 ≤ tau，0 ≤ u_k ≤ psi_k"""
        if len(psi_values) == 0:
            return 0.0

        prob = pulp.LpProblem(f"R2T_tau_{tau}", pulp.LpMaximize)

        # 创建变量 u_k
        u_vars = []
        for k in range(len(psi_values)):
            u_k = pulp.LpVariable(f'u_{k}', lowBound=0, upBound=psi_values[k])
            u_vars.append(u_k)

        # 目标函数：最大化总和
        prob += pulp.lpSum(u_vars)

        # 约束：每个客户的总贡献 ≤ tau
        for c_j in c_j_sets:
            if c_j:
                prob += pulp.lpSum([u_vars[k] for k in c_j]) <= tau

        # 求解
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)
        prob.solve(solver)

        if prob.status == pulp.LpStatusOptimal:
            return pulp.value(prob.objective)
        return None

    def r2t_count_single(self, beta: float = 0.5, verbose: bool = False):
        """单次COUNT查询 - 全表版本"""
        # 真实结果
        true_answer = self.get_true_count()

        # 准备数据
        psi_values, c_j_sets = self.prepare_count_data()
        ds_q = self.compute_ds_q(c_j_sets, psi_values)

        # 参数设置
        gs_q = max(10 ** 6, int(ds_q * 2))
        log_gs = int(math.log2(gs_q)) + 1
        penalty = log_gs * math.log(log_gs / beta)

        # 生成τ值（指数增长，覆盖到2×DS_Q）
        tau_values = []
        tau = 2
        max_tau = int(ds_q * 2)
        while tau <= max_tau:
            tau_values.append(tau)
            tau = int(tau * 1.5)

        if verbose:
            print(f"\n  真实值: {true_answer:,.0f}")
            print(f"  DS_Q: {ds_q:,.0f}")
            print(f"  GS_Q: {gs_q:,}, log_gs: {log_gs}, penalty: {penalty:.2f}")
            print(f"  τ范围: {tau_values[0]:,} - {tau_values[-1]:,} (共{len(tau_values)}个)")

        # 对每个τ求解LP
        noisy_estimates = []
        tau_results = []

        for tau in tau_values:
            q_tau = self.solve_lp(psi_values, c_j_sets, tau)

            if q_tau is not None:
                scale = (log_gs * tau) / self.epsilon
                noise = np.random.laplace(0, scale)
                noisy = q_tau + noise - (penalty * tau / self.epsilon)
                noisy_estimates.append(noisy)
                tau_results.append((tau, q_tau, noisy))

        # 选择最优τ
        if noisy_estimates:
            best_idx = np.argmax(noisy_estimates)
            best_tau, best_q, best_noisy = tau_results[best_idx]

            error = abs(best_noisy - true_answer)
            rel_error = error / true_answer * 100 if true_answer > 0 else 0

            return {
                'type': 'COUNT',
                'true_answer': true_answer,
                'private_result': best_noisy,
                'chosen_tau': best_tau,
                'error': error,
                'relative_error': rel_error,
                'ds_q': ds_q,
                'gs_q': gs_q
            }

        return None

    def r2t_sum_single(self, beta: float = 0.5, verbose: bool = False):
        """单次SUM查询 - 全表版本"""
        # 真实结果
        true_answer = self.get_true_sum()

        # 准备数据
        psi_values, c_j_sets = self.prepare_sum_data()
        ds_q = self.compute_ds_q(c_j_sets, psi_values)

        # 参数设置
        gs_q = max(10 ** 6, int(ds_q * 2))
        log_gs = int(math.log2(gs_q)) + 1
        penalty = log_gs * math.log(log_gs / beta)

        # 生成τ值
        tau_values = []
        tau = 2
        max_tau = int(ds_q * 2)
        while tau <= max_tau:
            tau_values.append(tau)
            tau = int(tau * 1.5)

        if verbose:
            print(f"\n  真实值: {true_answer:,.2f}")
            print(f"  DS_Q: {ds_q:,.2f}")
            print(f"  GS_Q: {gs_q:,}, log_gs: {log_gs}, penalty: {penalty:.2f}")
            print(f"  τ范围: {tau_values[0]:,} - {tau_values[-1]:,} (共{len(tau_values)}个)")

        # 对每个τ求解LP
        noisy_estimates = []
        tau_results = []

        for tau in tau_values:
            q_tau = self.solve_lp(psi_values, c_j_sets, tau)

            if q_tau is not None:
                scale = (log_gs * tau) / self.epsilon
                noise = np.random.laplace(0, scale)
                noisy = q_tau + noise - (penalty * tau / self.epsilon)
                noisy_estimates.append(noisy)
                tau_results.append((tau, q_tau, noisy))

        # 选择最优τ
        if noisy_estimates:
            best_idx = np.argmax(noisy_estimates)
            best_tau, best_q, best_noisy = tau_results[best_idx]

            error = abs(best_noisy - true_answer)
            rel_error = error / true_answer * 100 if true_answer > 0 else 0

            return {
                'type': 'SUM',
                'true_answer': true_answer,
                'private_result': best_noisy,
                'chosen_tau': best_tau,
                'error': error,
                'relative_error': rel_error,
                'ds_q': ds_q,
                'gs_q': gs_q
            }

        return None

    def run_multiple_trials(self, query_type: str = 'count',
                            num_trials: int = 10, beta: float = 0.5):
        """运行多次试验"""
        print(f"\n{'=' * 70}")
        print(f"📊 {query_type.upper()}查询 - {num_trials}次试验")
        print(f"{'=' * 70}")

        results = []
        for i in range(num_trials):
            print(f"\n--- 试验 {i + 1}/{num_trials} ---")

            if query_type == 'count':
                result = self.r2t_count_single(beta, verbose=True)
            else:
                result = self.r2t_sum_single(beta, verbose=True)

            if result:
                results.append(result)
                print(f"   相对误差: {result['relative_error']:.2f}%")

        if not results:
            print("❌ 没有成功的试验结果")
            return None

        # 统计
        errors = [r['error'] for r in results]
        rel_errors = [r['relative_error'] for r in results]
        chosen_taus = [r['chosen_tau'] for r in results]

        print(f"\n{'=' * 70}")
        print(f"📈 {query_type.upper()}查询 - 统计结果")
        print(f"{'=' * 70}")
        print(f"真实结果: {results[0]['true_answer']:,.2f}")
        print(f"DS_Q: {results[0]['ds_q']:,.2f}")
        print()
        print(f"误差统计:")
        print(f"  平均误差: {np.mean(errors):,.2f} (±{np.std(errors):,.2f})")
        print(f"  最小误差: {np.min(errors):,.2f}")
        print(f"  最大误差: {np.max(errors):,.2f}")
        print()
        print(f"相对误差:")
        print(f"  平均: {np.mean(rel_errors):.2f}%")
        print(f"  中位数: {np.median(rel_errors):.2f}%")
        print(f"  标准差: {np.std(rel_errors):.2f}%")
        print(f"  最小: {np.min(rel_errors):.2f}%")
        print(f"  最大: {np.max(rel_errors):.2f}%")
        print()
        print(f"选择的τ:")
        print(f"  平均: {np.mean(chosen_taus):.0f}")
        print(f"  范围: {np.min(chosen_taus)} - {np.max(chosen_taus)}")

        return {
            'mean_error': np.mean(errors),
            'std_error': np.std(errors),
            'mean_rel_error': np.mean(rel_errors),
            'median_rel_error': np.median(rel_errors),
            'std_rel_error': np.std(rel_errors),
            'min_rel_error': np.min(rel_errors),
            'max_rel_error': np.max(rel_errors),
            'mean_tau': np.mean(chosen_taus)
        }


def main():
    """主函数 - 运行多次试验"""
    print("=" * 70)
    print("🎯 R2T算法完整测试 - 全表查询版本")
    print("=" * 70)

    db_path = "tpch.db"

    import os
    if not os.path.exists(db_path):
        print(f"❌ 数据库不存在: {db_path}")
        print("请先运行 step2_create_sqlite_db_working.py 创建数据库")
        return

    r2t = R2TComplete(db_path, epsilon=1.0)

    try:
        r2t.connect()

        # COUNT查询 - 10次试验
        count_stats = r2t.run_multiple_trials('count', num_trials=10, beta=0.5)

        # SUM查询 - 10次试验
        sum_stats = r2t.run_multiple_trials('sum', num_trials=10, beta=0.5)

        # 最终汇总
        print("\n" + "=" * 70)
        print("📋 最终结果汇总")
        print("=" * 70)

        if count_stats:
            print(f"\n📊 COUNT查询 (10次试验平均):")
            print(f"   平均相对误差: {count_stats['mean_rel_error']:.2f}%")
            print(f"   中位数相对误差: {count_stats['median_rel_error']:.2f}%")
            print(f"   标准差: {count_stats['std_rel_error']:.2f}%")
            print(f"   误差范围: {count_stats['min_rel_error']:.2f}% - {count_stats['max_rel_error']:.2f}%")

        if sum_stats:
            print(f"\n💰 SUM查询 (10次试验平均):")
            print(f"   平均相对误差: {sum_stats['mean_rel_error']:.2f}%")
            print(f"   中位数相对误差: {sum_stats['median_rel_error']:.2f}%")
            print(f"   标准差: {sum_stats['std_rel_error']:.2f}%")
            print(f"   误差范围: {sum_stats['min_rel_error']:.2f}% - {sum_stats['max_rel_error']:.2f}%")

        # 判断优化效果
        if count_stats and sum_stats:
            avg_error = (count_stats['mean_rel_error'] + sum_stats['mean_rel_error']) / 2
            print("\n" + "=" * 70)
            if avg_error < 10:
                print("🎉 优化成功！平均相对误差 < 10%")
            elif avg_error < 20:
                print("📈 平均相对误差在10-20%之间，可接受")
            else:
                print("⚠️ 平均相对误差 > 20%，建议进一步调整参数")

    finally:
        r2t.close()


if __name__ == "__main__":
    main()