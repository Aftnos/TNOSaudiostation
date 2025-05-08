import requests
import sys
from gui import Application

def main():
    app = Application()

if __name__ == "__main__":
    # 禁用SSL警告
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    main()