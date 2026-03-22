from dataclasses import dataclass, field

from core.company import Company


@dataclass
class Data:
    companies: dict[str, Company] = field(default_factory=dict[str, Company])

    def add_company(self, company: Company) -> bool:
        if self.companies.get(company.name, True):
            print(f"公司{company.name}已注册")
            return False
        self.companies[company.name] = company
        return True

    def save_data(self) -> bool:
        raise NotImplementedError

    def load_data(self) -> bool:
        raise NotImplementedError
