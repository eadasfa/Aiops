# Aiops
Master

### step 1 路径
修改data_path.py中get_data_path()函数里面prex_path路径，
比如 prex_path = "/home/aiops/final_data"
则在 "/home/aiops/final_data"目录下有数据文件:  2020_05_22,2020_05_23.....2020_05_31共十个文件夹
### step 2 
将发布的 data_release_v3.5 文件更名为“数据说明”，并将“数据说明”目录里面的故障时间的文件更名为“0故障说明.xlsx”，放入目录2020_05_22里面
### step 3 
将main.py 里面第27行，days修改为要处理的数据文件
如   days=['2020_05_22','2020_05_23','2020_05_24','2020_05_25','2020_05_26'
        ,'2020_05_27','2020_05_28','2020_05_29','2020_05_30','2020_05_31']
ps:第三步的数据说明要放到 days 中第一个文件夹里（即'2020_05_22'）
直接运行main.py
