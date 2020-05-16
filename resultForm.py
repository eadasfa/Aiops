import data_path
import os
import csv
def resultForm(result):
    header=['fault_id','rank','category','cmdb_id','index']
    with open(os.path.join(data_path.get_save_path(), "resultForm.csv"), 'w') as f:
        writer=csv.writer(f)
        writer.writerow(header)
        for i, r in enumerate(result):
            fault_id = i + 1
            for rank in range(len(r)):
                row=[]
                if rank > 1:
                    break
                cmdb_id = r[rank][0]
                category=cmdb_id.split("_")[0]
                index=r[rank][1] if len(r)>1 else None
                row=[fault_id,rank,category,cmdb_id,index]
                print(row)
                writer.writerow(row)


