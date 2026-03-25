# core/services/company_registry.py

from core.domain.models import Company
from core.stores.company_store import CompanyStore


class CompanyRegistry:
    def __init__(self, company_store: CompanyStore) -> None:
        self.store = company_store
        self.companies: dict[str, Company] = {}

    def reload(self) -> None:
        """启动或数据更新时重载所有数据"""
        companies = self.store.load_all()
        self.companies = {company.id: company for company in companies}

    def get(self, company_id: str) -> Company | None:
        """通过公司 id 获取公司对象
        Args:
            company_id  : str 公司 id

        Returns:
            Company     : 存在该 id 的公司
            None        : 未找到该 id 的公司
        """
        return self.companies.get(company_id)
