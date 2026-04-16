import csv

def remove_rows_containing_substring_builtin(filepath, target_substring):
    """
    使用内置 csv 模块，只要某一行任意单元格【包含】目标字符串，就将其删除。
    """
    try:
        rows_to_keep = []
        
        # 1. 读取原 CSV 文件
        with open(filepath, mode='r', encoding='utf-8') as f:
            # 这次我们用普通的 reader，把它当作一个列表处理，更方便检查整行
            reader = csv.reader(f)
            
            # 2. 遍历每一行
            for row in reader:
                # 检查这一行（row 是一个列表）里，是否有任何一个单元格的字符串包含了目标字段
                # 如果没有任何单元格包含该字段，我们就保留这一行
                if not any(target_substring in str(cell) for cell in row):
                    rows_to_keep.append(row)
                    
        # 3. 将保留下来的行重新写入原文件
        with open(filepath, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows_to_keep) # 批量写入
            
        print(f"[成功] 已清理文件: {filepath}，所有包含 '{target_substring}' 的行均被移除。")
        
    except Exception as e:
        print(f"[错误] 处理文件时发生异常: {e}")

if __name__ == '__main__':
    csv_file = "status_report.csv"
    keyword_to_delete = "opt_traj"
    
    remove_rows_containing_substring_builtin(csv_file, keyword_to_delete)