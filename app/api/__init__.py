"""
API 模块 - 整合 API 调用、风控处理、用户管理
"""

from .client import (
    Client, 
    BuyerJson,
    AddressJson, 
    ProjectJson,
    confirmJson,
    prepareJson,
    createJson,
    myInfoJson,
    createStatusJson,
    ProjectInfoByDateJson
)
from .gaia import GaiaHandler

# 兼容: 保留旧名称 Api 指向 Client
Api = Client
