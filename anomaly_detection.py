# %%
import csv
import os
import numpy as np
import pandas as pd
from sklearn import preprocessing
import data_cleaning
import data_path
import matplotlib.pyplot as plt
from read_data import readCsvWithPandas, readCSV
from sklearn.ensemble import IsolationForest
n = 3
# path = os.path.join(data_path.get_data_path(), "调用链指标")

# %%


def find_time_interval(data):
    """
    在入口服务中，找到异常的数据的时间戳
    """
    avg_times = data[:, 2].astype(np.float32)
    # 大于1的数据舍弃，不去计算均值和方差
    avg_times_temp = list(filter(lambda x: x < 1, avg_times))
    succee_rate = data[:, 5].astype(np.float32)
    std = np.std(avg_times_temp, ddof=1)
    means = np.mean(avg_times_temp)

    high = means+3*std
    low = means-3*std
    # print(high,low)
    def lam(
        i): return avg_times[i] > high or avg_times[i] < low or succee_rate[i] < 1
    res = data[list(filter(lam,  range(len(data))))]
    return res[:, 1].astype(np.int64)


def to_period_time(timestamps, bias=1.5*60*1000):
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


def iforest(data, cols, n_estimators=100, n_jobs=-1, verbose=2):
    ilf = IsolationForest(n_estimators=n_estimators,
                          n_jobs=n_jobs,          # 使用全部cpu
                          verbose=verbose,
                          )
    # 选取特征，不使用标签(类型)
    X_cols = cols
    print(data.shape)
    # 训练
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
    
def fault_time(bias=0):
    """[summary]
    直接读文件读出 故障时间
    """
    table = read_xlrd(os.path.join(
        data_path.get_data_path(), "数据说明", "0故障内容.xlsx"))
    table_head = table.row_values(0)
    time_index, duration_index = 0, 0
    for i in range(table.ncols):
        if table_head[i] == 'time':
            time_index = i
        elif table_head[i] == 'duration':
            duration_index = i
    res = []
    for i in range(1, table.nrows):
        row = table.row_values(i)
        cell = table.cell_value(i, time_index)
        date = datetime(*xldate_as_tuple(cell, 0))
        # print(date)
        time_stamp = int(datetime.timestamp(date))*1000
        duration = int(re.match('\d*', row[duration_index])[0])*60*1000
        res.append([time_stamp, time_stamp+duration])
    return res

def draw_abnormal_period(data,period_times=None):
    # 找到的画出异常时间段
    x = range(len(data))

    index = [[] for _ in range(len(period_times))]
    for i,d in enumerate(data[:, 1].astype(np.int64)):
        for j,t in enumerate(period_times):
            if d<t[1] and d>t[0]:
                index[j].append(i)

    plt.figure(figsize=(8, 5))
    # 获取平均处理时间一列
    y = data[:, 2].astype(np.float32)
    plt.subplot(2, 1, 1)
    # plt.title("平均调用时间")
    plt.plot(x, y, label="平均调用时间")
    for i in index:
        plt.plot(i,np.ones(len(i))*40,color='y')

    # 获取成功率一列
    y = data[:, 5].astype(np.float32)
    plt.subplot(2, 1, 2)
    # plt.title("成功率")
    plt.plot(x, y, color='r', label="成功率")
    
        
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

# %%
