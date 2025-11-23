import sys
import os
from streamlit.web import cli as stcli

def main():
    # 获取当前脚本的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 目标文件的路径
    target_file = os.path.join(current_dir, "hotspot.py")
    
    # 构造启动命令: streamlit run hotspot.py
    sys.argv = ["streamlit", "run", target_file]
    
    # 执行命令
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()