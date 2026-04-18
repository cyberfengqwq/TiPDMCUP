# core/stores/company_store.py

from datetime import datetime

from core.domain.models import Company
from core.stores.base_json_store import BaseJsonStore


class CompanyStore(BaseJsonStore):
    """
    公司部分的 Json 处理类
    """

    def load_all(self) -> list[Company]:
        """载入 Json 文件中所有的公司，并实例化

        Returns:
            list[Company]: 所有实例化后的公司的列表
        """

        raw_data = self.read_json()

        if not raw_data:
            return []

        companies: list[Company] = []
        for item in raw_data:
            created_at = datetime.fromisoformat(item["created_at"])
            company = Company(
                id=item["id"],
                name=item["name"],
                status=item["status"],
                created_at=created_at,
            )

            companies.append(company)

        return companies

    def save_all(self, companies: list[Company]) -> None:
        """保存所有公司信息到 Json 文件

        Args:
            companies: list[Company] : 输入的包含所有公司对象的列表
        """

        raw_data = [
            {
                "id": company.id,
                "name": company.name,
                "status": company.status,
                "created_at": company.created_at.isoformat(),
            }
            for company in companies
        ]

        self.write_json_atomic(raw_data)

    def update(self, company: Company) -> None:
        """更新公司信息
        Args:
            company: Company 要更新的单个公司对象

        """

        companies: list[Company] = self.load_all()
        updated = False
        for i, existing_company in enumerate(companies):
            if existing_company.id == company.id:
                companies[i] = company
                updated = True
                break

        if not updated:
            companies.append(company)

        self.save_all(companies)
