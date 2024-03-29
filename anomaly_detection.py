#coding:utf-8
# %%
import csv
import os
import numpy as np
import pandas as pd
from sklearn import preprocessing
import data_cleaning
import data_path
import re
import matplotlib.pyplot as plt
from read_data import readCsvWithPandas, readCSV,read_xlrd
from datetime import datetime
from xlrd import xldate_as_tuple
from sklearn.ensemble import IsolationForest
# import rrcf
n = 3
# path = os.path.join(data_path.get_data_path(), "调用链指标")

plt.rcParams['font.sans-serif']=['SimHei'] #用来正常显示中文标签
plt.rcParams['axes.unicode_minus']=False #用来正常显示负号
# %%

# k sigma 算法
def find_abnormal_data(data, k=3):
    """
    在入口服务中，找到异常的数据的时间戳
    data: [serviceName,startTime,avg_time,num,succee_num,succee_rate]
    return: np.array(),返回异常数据
    """
    avg_times = data[:, 2].astype(np.float32)
    # 大于1的数据舍弃，不去计算均值和方差
    avg_times_temp = list(filter(lambda x: x < 1, avg_times))
    succee_rate = data[:, 5].astype(np.float32)
    std = np.std(avg_times_temp, ddof=1)
    means = np.mean(avg_times_temp)

    high = means+k*std
    low = means-k*std
    # print(high,low)
    def lam(i): return avg_times[i] > high or avg_times[i] < low or succee_rate[i] < 1
    res = data[list(filter(lam,  range(len(data))))]
    return res


def to_interval(timestamps, bias=3*60*1000):
    '''
    将时间戳的序列转换为时间段,区间合并
    '''
    def merge(intervals):
        intervals.sort(key=lambda x: x[0])

        merged = []
        for interval in intervals:
            # 如果列表为空，或者当前区间与上一区间不重合，直接添加
            if not merged or merged[-1][1] < interval[0]:
                merged.append(interval)
            else:
                # 否则的话，我们就可以与上一区间进行合并
                merged[-1][1] = max(merged[-1][1], interval[1])
        return merged
    r = list(map(lambda t: [t-bias, t+bias], timestamps))
    return merge(r)

def is_net_error_func(intervals,abnormal_data, n=0.9):
    '''
    abnormal_data: [serviceName,startTime,avg_time,num,succee_num,succee_rate]，异常数据
    '''
    timestamps = abnormal_data[:, 1].astype(np.float32)
    succee_rates = abnormal_data[:, 5].astype(np.float32)

    is_net_error = []
    for interval in intervals:
        total, succee_rate_equal_one = 0, 0
        start,end = interval[0],interval[1]
        for timestamp, succee_rate in zip(timestamps,succee_rates):
            if timestamp > start and timestamp < end:
                succee_rate_equal_one += 1 if float(succee_rate)>=1 else 0
                total += 1
        # print(total, succee_rate_equal_one)
        succee_rate_not_equal_one = total-succee_rate_equal_one
        # print(succee_rate_equal_one,total,succee_rate_equal_one/total)
        is_net_error.append(succee_rate_equal_one/total > n)
    return is_net_error

def RRCF(data,num_trees=40,shingle_size=4,tree_size=128):
    """[Robust Random Cut Forest]
    Args:
        num_trees ([type]): [森林中树的数量]]
        shingle_size ([type]): [窗口大小]
        tree_size ([type]): [树的大小，即树中有多少叶子节点]
        data ([type]): [数据]
    Returns:
        [type]: [每一行数据的平局得分]
    """
    # forest = []
    # for _ in range(num_trees):
    #     tree = rrcf.RCTree()
    #     forest.append(tree)
    # points = rrcf.shingle(data, size=shingle_size)
    # avg_codisp = {}
    # for index, point in enumerate(points):
    #     # For each tree in the forest...
    #     for tree in forest:
    #         # If tree is above permitted size, drop the oldest point (FIFO)
    #         if len(tree.leaves) > tree_size:
    #             tree.forget_point(index - tree_size)
    #         # Insert the new point into the tree
    #         tree.insert_point(point, index=index)
    #         # Compute codisp on the new point and take the average among all trees
    #         if not index in avg_codisp:
    #             avg_codisp[index] = 0
    #         avg_codisp[index] += tree.codisp(index) / num_trees
    # avg_codisp = list(map(lambda x:x[1], sorted(avg_codisp.items(),key=lambda y:y[0])))
    # return avg_codisp
    pass
    
def iforest(data, cols, n_estimators=100, n_jobs=-1, verbose=2):
    ilf = IsolationForest(n_estimators=n_estimators,
                          n_jobs=n_jobs,          # 使用全部cpu
                          verbose=verbose,
                          )
    # 选取特征，不使用标签(类型)
    X_cols = cols
    print(data.shape)
    # 训练， 根据列名训练
    ilf.fit(data[X_cols])
    shape = data.shape[0]
    batch = 10**6
    
    all_pred = []
    for i in range(shape//batch+1):
        start = i * batch
        end = (i+1) * batch
        test = data[X_cols][start:end]
        # 预测
        pred = ilf.predict(test)
        all_pred.extend(pred)
    # data['pred'] = all_pred
    # data.to_csv('outliers.csv', columns=["pred", ], header=False)
    return np.array(all_pred)

def fault_time(file_day,bias=0,type = 0):
    """[summary]
    直接读文件读出 故障时间
    file_day: 数据说明所在的目录
    """
    table = read_xlrd(os.path.join(
        data_path.data_instruction_path, "0故障说明.xlsx"))
    table_head = table.row_values(0)
    time_index, duration_index,fault_id_index = 0, 0, 0
    for i in range(table.ncols):
        if 'time' in table_head[i] :
            time_index = i
        elif table_head[i] == 'duration':
            duration_index = i
        elif "fault_id" == table_head[i] :
            fault_id_index = i
    print(time_index,duration_index)
    res ,fault_ids =[], []
    for i in range(1, table.nrows):
        row = table.row_values(i)
        cell = table.cell_value(i, time_index)
        date = datetime(*xldate_as_tuple(cell, 0))
        # print(date)
        time_stamp = int(datetime.timestamp(date))*1000
        duration = int(re.match('\d*', row[duration_index])[0])*60*1000+bias
        res.append([time_stamp, time_stamp+duration])
        fault_ids.append(int(row[fault_id_index]))
    if type==0:
        return res
    if type==1:
        return fault_ids
    if type==2:
        return res,fault_ids

def draw_abnormal_period(data,period_times=None):
    # 找到的画出异常时间段
    x = range(len(data))

    index = [[] for _ in range(len(period_times))]
    for i,d in enumerate(data[:, 1].astype(np.int64)):
        for j,t in enumerate(period_times):
            if d<t[1] and d>t[0]:
                index[j].append(i)

    plt.figure(figsize=(8, 5))
    #! 第一个图
    plt.subplot(2, 1, 1)
    # 获取平均处理时间一列
    y = data[:, 2].astype(np.float32)
    # plt.title("平均调用时间")
    plt.plot(x, y, label="平均调用时间")
    for i in index:
        plt.plot(i,np.ones(len(i))*40,color='y')
    # plt.title('平均调用时间')
    plt.ylabel('平均调用时间')
    plt.xlabel('时间轴')


    #! 第二个图
    plt.subplot(2, 1, 2)
    # 获取成功率一列
    y = data[:, 5].astype(np.float32)
    # plt.title("成功率")
    plt.plot(x, y, color='r', label="成功率")
    plt.ylabel('成功率')
    plt.xlabel('时间轴')
    for i in index:
        plt.plot(i,np.ones(len(i))*0.5,color='y')

    plt.show()
# # 业务指标
# # %%读取数据
# business_path = os.path.join(data_path.get_data_path(), "业务指标", "esb.csv")
# data = pd.read_csv(business_path)
# data.sort_values("startTime",inplace=True)
# print(data.head(5))

# # %%
# timestamps = find_time_interval(data.values)
# interval_times = to_period_time(timestamps)
# print(interval_times)

# # %%
# pred = iforest(data,["avg_time","succee_rate"])
# #%%
# timestamps = data[pred==-1]["startTime"].values
# interval_times = to_period_time(timestamps)
# print(len(interval_times))
# for t in interval_times:
#     print(t)
# print(fault_time())
# %%
if __name__ == "__main__":

    day = "2020_05_22"
    # 业务指标
    business_path = os.path.join(data_path.get_data_path(day), "业务指标", "esb.csv")

    # 获取业务指标数据，去掉表头,np.array
    data = readCsvWithPandas(business_path)
    # 根据时间序列排序
    data = data[np.argsort(data[:, 1])]
    # todo step1 异常时间序列
    # 异常数据
    abnormal_data = find_abnormal_data(data)
    # 异常时间序列
    execption_times = abnormal_data[:, 1].astype(np.int64)
    # 异常时间区间
    interval_times = to_interval(execption_times)
    is_net_error = is_net_error_func(interval_times,abnormal_data)
    print(len(interval_times))
    # period_times = anomaly_detection.fault_time()
    for i,j in zip(interval_times,is_net_error):
        print(i,j)
    # 画出找到的异常区间
    draw_abnormal_period(data, interval_times)
# %%
