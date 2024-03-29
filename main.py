# %%
import numpy as np
import pandas as pd
import importlib
import os
import sys
import re
import json
import matplotlib.pyplot as plt
import data_path  # 路径
import data_cleaning
from read_data import readCSV, read_xlrd, readCsvWithPandas
from datetime import datetime
from xlrd import xldate_as_tuple
from show_Kpis import getKpis
import anomaly_detection
import network
import resultForm
#%%
kpi_opened = {}
left_n = 10  # 保留几个结果
# 是否是执行者调用
isExecutor = {"JDBC": False, "LOCAL": False, "CSF": False,
              "FlyRemote": True, "OSB": True, "RemoteProcess": True}
# 哪一天的数据
# days = ['2020_05_22']
days=['2020_05_22','2020_05_23','2020_05_24','2020_05_25','2020_05_26'
    ,'2020_05_27','2020_05_28','2020_05_29','2020_05_30','2020_05_31']
# %%


def find_abnormal_indicators(execption_Interval, cmdb_id,paths):
    """[该时间区间内那个指标错误]

    Args:
        execption_Interval ([type]): [时间区间]
        cmdb_id ([type]): [网源]
        paths list: [path1,path2]
    """
    kpis = {}
    abnormal_indicators = []
    # os,docker,db
    file_name = data_path.fileNames[cmdb_id.split('_')[0]]
    # file_path = os.path.join(data_path.get_data_path(),"平台指标",file_name)
    # 查看当前文件是否已经分解
    if kpi_opened.get(file_name) == None:
        for p in paths:
            kpis=getKpis([file_name],p,kpis)
        kpi_opened[file_name] = kpis
    else:
        kpis = kpi_opened[file_name]
    # 逐个指标的进行判断
    for k, v in kpis.items():
        temp = k.split(',')  # (cmdb_id,name,bomc_id,itemid)
        if cmdb_id == temp[0]:
            # todo 进行异常评估，给出得分
            score = anomaly_detection_func(execption_Interval, np.array(v))
            abnormal_indicators.append([temp[0], temp[1], temp[2], score])
    # 排序返回得分最高的三个
    return abnormal_indicators
def anomaly_detection_func_by_RRCF(execption_Interval, data):
    """[异常检测算法]

    Args:
        execption_Interval ([tutle]): [时间区间(start_time,end_time)]
        data ([type]): [itemid,name,bomc_id,timestamp,valuee,cmdb_id]
    """
    data = pd.DataFrame(data)
    data.columns = ['itemid', 'name', 'bomc_id',
                    'timestamp', 'value', 'cmdb_id']
    # 根据时间戳排序
    data.sort_values("timestamp", inplace=True)
    # 得到预测值
    pred = anomaly_detection.RRCF(data=data['value'].values.astype(np.float64),num_trees=40,shingle_size=4,tree_size=256)
    # data['pred'] = pred
    # data.to_csv('outliers2.csv', columns=["timestamp",'value',"pred", ], header=False)
    timestamps = data['timestamp'].values.astype(np.int64)
    total, abnormal_data_total = 0, 0
    for timestamp, pred_num in zip(timestamps, pred):
        if timestamp < execption_Interval[1] and timestamp > execption_Interval[0]:
            total += 1
            abnormal_data_total += pred_num

    return abnormal_data_total/total


def anomaly_detection_func(execption_Interval, data):
    """[异常检测算法]

    Args:
        execption_Interval ([tutle]): [时间区间(start_time,end_time)]
        data ([type]): [itemid,name,bomc_id,timestamp,valuee,cmdb_id]
    """
    data = pd.DataFrame(data)
    data.columns = ['itemid', 'name', 'bomc_id',
                    'timestamp', 'value', 'cmdb_id']
    # 根据时间戳排序
    data.sort_values("timestamp", inplace=True)
    # 得到预测值
    pred = anomaly_detection.iforest(data, ["value"])
    # data['pred'] = pred
    # data.to_csv('outliers2.csv', columns=["timestamp",'value',"pred", ], header=False)
    timestamps = data['timestamp'].values.astype(np.int64)
    total, abnormal_data_total = 0, 0
    for timestamp, pred_num in zip(timestamps, pred):
        if timestamp < execption_Interval[1] and timestamp > execption_Interval[0]:
            total += 1
            abnormal_data_total += 1 if pred_num == -1 else 0

    return abnormal_data_total


def find_abnormal_span(trace):
    """按照图的遍历方式遍历trace中的所有span\n
    Args:
        trace ([dict]): 一条trace，格式{ startTime:str,{spanId:{},spanId:{}}}        \n
    Returns:
        [list]: 返回异常节点       \n
    """
    spans = trace['spans']
    graph = data_cleaning.generateGraph(spans)
    if graph.get('root') == None:
        return []
    abnormal_cmdb_ids = []
    Break = True
    # isError代表上溯的节点是否有异常
    def traverse(root_id, abn_ids, isError=False):
        root = spans[root_id]
        # 如果上溯有异常或本身有异常
        if isError or root['success'] == 'False':
            # 当发现是数据库出现问题时，将其他的清空，只保存数据库cmdb_id,并退出递归
            if root['db'] and root['success'] == 'False':
                abn_ids.clear()
                abn_ids.append(root["db"])
                return Break
            # 找出上一个失败的下一个成功
            if isExecutor[root['callType']] and root['callType'] != 'OSB' \
                    and root['success'] == 'True':
                abn_ids.clear()
                abn_ids.append(root["cmdb_id"])
        isError = root['success'] == 'False'
        # 如果没有子节点，直接返回
        if graph.get(root_id) == None:
            return not Break
        for span_id in graph[root_id]:
            if traverse(span_id, abn_ids, isError) == Break:
                return Break
        return not Break

    for span_id in graph.get('root'):
        abn_ids = []
        traverse(span_id, abn_ids)
        abnormal_cmdb_ids += abn_ids
    return abnormal_cmdb_ids


def find_abnormal_trace(execption_Interval, traces):
    """找到改异常区间内所有trace

    Args:
        execption_Interval ([type]): [时间区间]
        traces ([type]): [description]
    """
    abnormal_trace = []
    for trace in traces.values():
        startTime = int(trace['startTime'])
        if startTime > execption_Interval[0] and startTime < execption_Interval[1]:
            abnormal_trace.append(trace)
    return abnormal_trace

def to_standard_answer(result,fault_ids):
    answer = {}
    # 异常时间段
    for fault_id, a_result in zip(fault_ids,result):
        if len(a_result)==0 or (len(a_result)==1 and len(a_result[0])==0):
            continue
        cmdb = a_result[0][0].split("_")[0] # docker
        answer[fault_id]=[ cmdb, a_result[0][0] ] # docker_001
        if len(a_result)==1:
            answer[fault_id].extend(a_result[0][1:])
            answer[fault_id].append([None])
        else:
        # 每一个异常时间段有多个指标
            indicator_list = [an_indicator[1] for an_indicator in a_result]
            answer[fault_id].append(indicator_list)
    return answer

## 得到异常时间段
def get_abnormal_interval(days, useGiven=True):
    business_paths = [os.path.join(data_path.get_data_path(day), "业务指标", "esb.csv") for day in days]
    # 获取业务指标数据，去掉表头,np.array
    data = None
    for p in business_paths:
        data = pd.concat([data,pd.read_csv(p)],ignore_index=True)
    data = data.values
    # 根据时间序列排序
    data = data[np.argsort(data[:, 1])]

    ## !异常时间区间
    interval_times, fault_ids = [], []
    
    # 根据给出的异常文档找出异常时间段
    if useGiven:
        interval_times,fault_ids = anomaly_detection.fault_time(bias=0*60*100,file_day=days[0],type=2)
    else: ## 通过自己算法找出
        # 异常数据
        abnormal_data = anomaly_detection.find_abnormal_data(data)
        # 异常时间序列
        execption_times = abnormal_data[:, 1].astype(np.int64)
        #! 异常时间区间
        interval_times = anomaly_detection.to_interval(execption_times)
        fault_ids = range(len(interval_times))
   

    print(str(interval_times))
    #! 对应时间区间是否是网络故障
    is_net_error =[]# anomaly_detection.is_net_error_func(interval_times,abnormal_data)
    for i,j in zip(interval_times,is_net_error):
        print(i,j)
    # 画出找到的异常区间
    anomaly_detection.draw_abnormal_period(data, interval_times)

    return interval_times,is_net_error,fault_ids
# %%
# 调用链指标,平台指标,数据说明
# importlib.reload(anomaly_detection)
plat_paths = [os.path.join(data_path.get_data_path(day),"平台指标") for day in days]
interval_times,is_net_error,fault_ids = get_abnormal_interval(days)
# print(fault_ids)
# %%
days=['2020_05_22']
# ,'2020_05_23','2020_05_24','2020_05_25','2020_05_26'
#     ,'2020_05_27','2020_05_28','2020_05_29','2020_05_30','2020_05_31']
# todo step2 获取所有trace
traces = {}
for day in days:
    prex_path = data_path.get_data_path(day)
    trace_p = os.path.join(prex_path,"调用链指标")
    data_cleaning.build_trace(trace_p,traces)

# %%
abnormal_cmdb_all = []
# 结果..
result = [ 0 for _ in range(len(interval_times))]
#? 遍历每一个时间端
for i in range(len(interval_times)):
    # 异常时间区间
    execption_Interval = interval_times[i]
    # 异常指标
    abnormal_indicators = []
    # todo step3 找出这段时间内的trace
    abnormal_traces = find_abnormal_trace(execption_Interval, traces)
    trace = []
    # 如果是网络故障
    # print(is_net_error[i])
    # if is_net_error[i]:
    if False:
        #do something
        net_error_cmdb_id = network.locate_net_error(abnormal_traces)
        abnormal_cmdb_all.append(net_error_cmdb_id)
        abnormal_indicators.append( net_error_cmdb_id )
    else :
        # abnormal_traces trace 中定位到具的体节点，即cmdb_id
        abnormal_cmdb_ids = list(set(network.locate_net_error(abnormal_traces)))
        # todo step4 找出异常数据中的异常节点
        for trace in abnormal_traces:
            abnormal_cmdb_ids += find_abnormal_span(trace)
        # 去重
        abnormal_cmdb_ids = list(set(abnormal_cmdb_ids))
        
        abnormal_cmdb_all.append(abnormal_cmdb_ids)
        # todo step5 判断网元节点中是哪个指标有异常
        for cmdb_id in abnormal_cmdb_ids:
            # ? 找到异常指标c 
            abnormal_indicators.extend(find_abnormal_indicators(
                execption_Interval, cmdb_id,plat_paths))
            print(execption_Interval, cmdb_id)
        # 对得到的异常指标进行排序
        abnormal_indicators = sorted(
            abnormal_indicators, key=lambda x: x[-1], reverse=True)[:left_n]
        if len(abnormal_indicators) !=0 and int(abnormal_indicators[0][-1])==0:
            abnormal_indicators = [abnormal_cmdb_ids]
    result[i] = np.array(abnormal_indicators)


for i in abnormal_cmdb_all:
    print(i)

# %%


print(len(result))
# for i in result:
#     print(i)
save_path = data_path.result_save_path()
if not os.path.exists(save_path):
    os.mkdir(save_path)
with open(os.path.join(save_path,"result_"+days[0]), 'w') as f:
    for fault_id, r in zip(fault_ids,result):
        f.write(str(fault_id)+":\n")
        for o in r:
            f.write(str(o)+'\n')
resultForm.resultForm(result,"result_"+days[0],fault_ids)

answer = to_standard_answer(result,fault_ids)
with open(os.path.join(save_path,"answer_"+days[0]+".json"), 'w') as f:
    js = json.dumps(answer, indent=2)
    f.write(js)

# %%

