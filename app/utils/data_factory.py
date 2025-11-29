"""
Data Factory - Dummy Data Generator

Generates realistic dummy data for testing without using LLM tokens.
"""

import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid


class DataType(str, Enum):
    """Data types for generation"""
    USER = "user"
    ORGANIZATION = "organization"
    PRODUCT = "product"
    CUSTOMER = "customer"
    ORDER = "order"
    INVOICE = "invoice"
    EMPLOYEE = "employee"
    PROJECT = "project"
    TASK = "task"
    SALES = "sales"


class DataFactory:
    """Factory for generating dummy data"""
    
    # Sample data pools
    FIRST_NAMES = [
        "John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa",
        "James", "Mary", "William", "Patricia", "Richard", "Jennifer", "Thomas",
        "Linda", "Charles", "Barbara", "Daniel", "Elizabeth", "Matthew", "Susan"
    ]
    
    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
    ]
    
    COMPANY_PREFIXES = [
        "Tech", "Global", "Digital", "Smart", "Innovative", "Advanced", "Premier",
        "Elite", "Dynamic", "Strategic", "Quantum", "Nexus", "Apex", "Vertex"
    ]
    
    COMPANY_SUFFIXES = [
        "Solutions", "Systems", "Technologies", "Enterprises", "Group", "Corp",
        "Industries", "Services", "Consulting", "Partners", "Labs", "Dynamics"
    ]
    
    PRODUCT_ADJECTIVES = [
        "Premium", "Professional", "Enterprise", "Standard", "Basic", "Advanced",
        "Ultimate", "Essential", "Pro", "Plus", "Deluxe", "Elite"
    ]
    
    PRODUCT_TYPES = [
        "Software", "Platform", "Suite", "Tool", "Service", "System", "Solution",
        "Application", "Framework", "Engine", "Module", "Package"
    ]
    
    DEPARTMENTS = [
        "Engineering", "Sales", "Marketing", "HR", "Finance", "Operations",
        "Customer Success", "Product", "Design", "Legal", "IT", "Support"
    ]
    
    JOB_TITLES = [
        "Manager", "Director", "Engineer", "Analyst", "Specialist", "Coordinator",
        "Lead", "Senior", "Junior", "Associate", "Executive", "Administrator"
    ]
    
    CITIES = [
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
        "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville"
    ]
    
    STATES = [
        "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI", "NJ", "VA"
    ]
    
    DOMAINS = [
        "gmail.com", "yahoo.com", "outlook.com", "company.com", "business.com",
        "enterprise.com", "tech.com", "solutions.com"
    ]
    
    @staticmethod
    def random_string(length: int = 10) -> str:
        """Generate random string"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def random_email(first_name: str = None, last_name: str = None) -> str:
        """Generate random email"""
        if not first_name:
            first_name = random.choice(DataFactory.FIRST_NAMES).lower()
        if not last_name:
            last_name = random.choice(DataFactory.LAST_NAMES).lower()
        domain = random.choice(DataFactory.DOMAINS)
        return f"{first_name}.{last_name}@{domain}"
    
    @staticmethod
    def random_phone() -> str:
        """Generate random phone number"""
        return f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"
    
    @staticmethod
    def random_date(start_days_ago: int = 365, end_days_ago: int = 0) -> datetime:
        """Generate random date"""
        start = datetime.now() - timedelta(days=start_days_ago)
        end = datetime.now() - timedelta(days=end_days_ago)
        delta = end - start
        random_days = random.randint(0, delta.days)
        return start + timedelta(days=random_days)
    
    @staticmethod
    def random_price(min_price: float = 10.0, max_price: float = 1000.0) -> float:
        """Generate random price"""
        return round(random.uniform(min_price, max_price), 2)
    
    @staticmethod
    def generate_user(organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate user data"""
        first_name = random.choice(DataFactory.FIRST_NAMES)
        last_name = random.choice(DataFactory.LAST_NAMES)
        
        return {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id or str(uuid.uuid4()),
            "email": DataFactory.random_email(first_name, last_name),
            "first_name": first_name,
            "last_name": last_name,
            "full_name": f"{first_name} {last_name}",
            "phone": DataFactory.random_phone(),
            "role": random.choice(["user", "manager", "admin", "viewer"]),
            "department": random.choice(DataFactory.DEPARTMENTS),
            "is_active": random.choice([True, True, True, False]),  # 75% active
            "created_at": DataFactory.random_date(365, 30),
            "last_login": DataFactory.random_date(30, 0)
        }
    
    @staticmethod
    def generate_organization() -> Dict[str, Any]:
        """Generate organization data"""
        prefix = random.choice(DataFactory.COMPANY_PREFIXES)
        suffix = random.choice(DataFactory.COMPANY_SUFFIXES)
        name = f"{prefix} {suffix}"
        
        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "slug": name.lower().replace(" ", "-"),
            "email": f"contact@{name.lower().replace(' ', '')}.com",
            "phone": DataFactory.random_phone(),
            "address": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Maple', 'Park'])} St",
            "city": random.choice(DataFactory.CITIES),
            "state": random.choice(DataFactory.STATES),
            "zip_code": f"{random.randint(10000, 99999)}",
            "country": "USA",
            "website": f"https://www.{name.lower().replace(' ', '')}.com",
            "industry": random.choice(["Technology", "Finance", "Healthcare", "Retail", "Manufacturing"]),
            "employee_count": random.choice([10, 50, 100, 500, 1000, 5000]),
            "subscription_tier": random.choice(["free", "basic", "professional", "enterprise"]),
            "is_active": True,
            "created_at": DataFactory.random_date(730, 30)
        }
    
    @staticmethod
    def generate_product() -> Dict[str, Any]:
        """Generate product data"""
        adjective = random.choice(DataFactory.PRODUCT_ADJECTIVES)
        product_type = random.choice(DataFactory.PRODUCT_TYPES)
        name = f"{adjective} {product_type}"
        
        return {
            "id": str(uuid.uuid4()),
            "sku": f"PRD-{DataFactory.random_string(8).upper()}",
            "name": name,
            "description": f"High-quality {name.lower()} for modern businesses",
            "category": random.choice(["Software", "Hardware", "Service", "Subscription"]),
            "price": DataFactory.random_price(50, 5000),
            "cost": DataFactory.random_price(20, 2000),
            "stock_quantity": random.randint(0, 1000),
            "reorder_level": random.randint(10, 100),
            "is_active": random.choice([True, True, True, False]),
            "created_at": DataFactory.random_date(365, 0)
        }
    
    @staticmethod
    def generate_customer(organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate customer data"""
        first_name = random.choice(DataFactory.FIRST_NAMES)
        last_name = random.choice(DataFactory.LAST_NAMES)
        
        return {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id or str(uuid.uuid4()),
            "email": DataFactory.random_email(first_name, last_name),
            "first_name": first_name,
            "last_name": last_name,
            "company": f"{random.choice(DataFactory.COMPANY_PREFIXES)} {random.choice(DataFactory.COMPANY_SUFFIXES)}",
            "phone": DataFactory.random_phone(),
            "address": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Maple'])} St",
            "city": random.choice(DataFactory.CITIES),
            "state": random.choice(DataFactory.STATES),
            "zip_code": f"{random.randint(10000, 99999)}",
            "customer_type": random.choice(["individual", "business"]),
            "status": random.choice(["active", "inactive", "prospect"]),
            "lifetime_value": DataFactory.random_price(100, 50000),
            "created_at": DataFactory.random_date(730, 0)
        }
    
    @staticmethod
    def generate_employee(organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate employee data"""
        first_name = random.choice(DataFactory.FIRST_NAMES)
        last_name = random.choice(DataFactory.LAST_NAMES)
        department = random.choice(DataFactory.DEPARTMENTS)
        
        return {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id or str(uuid.uuid4()),
            "employee_id": f"EMP-{random.randint(1000, 9999)}",
            "email": DataFactory.random_email(first_name, last_name),
            "first_name": first_name,
            "last_name": last_name,
            "phone": DataFactory.random_phone(),
            "department": department,
            "job_title": f"{random.choice(DataFactory.JOB_TITLES)} - {department}",
            "salary": DataFactory.random_price(40000, 200000),
            "hire_date": DataFactory.random_date(1825, 30),
            "status": random.choice(["active", "active", "active", "on_leave", "terminated"]),
            "manager_id": None,  # Can be set later
            "created_at": DataFactory.random_date(1825, 30)
        }
    
    @staticmethod
    def generate_sales_record(organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate sales record"""
        quantity = random.randint(1, 100)
        unit_price = DataFactory.random_price(10, 1000)
        
        return {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id or str(uuid.uuid4()),
            "order_number": f"ORD-{random.randint(10000, 99999)}",
            "customer_id": str(uuid.uuid4()),
            "product_id": str(uuid.uuid4()),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_amount": round(quantity * unit_price, 2),
            "discount": DataFactory.random_price(0, 100),
            "tax": DataFactory.random_price(0, 50),
            "status": random.choice(["pending", "completed", "shipped", "delivered", "cancelled"]),
            "sale_date": DataFactory.random_date(180, 0),
            "created_at": DataFactory.random_date(180, 0)
        }
    
    @staticmethod
    def generate_batch(data_type: DataType, count: int, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate batch of data"""
        generators = {
            DataType.USER: DataFactory.generate_user,
            DataType.ORGANIZATION: DataFactory.generate_organization,
            DataType.PRODUCT: DataFactory.generate_product,
            DataType.CUSTOMER: DataFactory.generate_customer,
            DataType.EMPLOYEE: DataFactory.generate_employee,
            DataType.SALES: DataFactory.generate_sales_record,
        }
        
        generator = generators.get(data_type)
        if not generator:
            raise ValueError(f"Unknown data type: {data_type}")
        
        # Generate data
        if data_type == DataType.ORGANIZATION:
            return [generator() for _ in range(count)]
        else:
            return [generator(organization_id) for _ in range(count)]


# Convenience functions
def generate_users(count: int = 10, organization_id: Optional[str] = None) -> List[Dict]:
    """Generate user data"""
    return DataFactory.generate_batch(DataType.USER, count, organization_id)


def generate_organizations(count: int = 5) -> List[Dict]:
    """Generate organization data"""
    return DataFactory.generate_batch(DataType.ORGANIZATION, count)


def generate_products(count: int = 20, organization_id: Optional[str] = None) -> List[Dict]:
    """Generate product data"""
    return DataFactory.generate_batch(DataType.PRODUCT, count, organization_id)


def generate_customers(count: int = 50, organization_id: Optional[str] = None) -> List[Dict]:
    """Generate customer data"""
    return DataFactory.generate_batch(DataType.CUSTOMER, count, organization_id)


def generate_employees(count: int = 25, organization_id: Optional[str] = None) -> List[Dict]:
    """Generate employee data"""
    return DataFactory.generate_batch(DataType.EMPLOYEE, count, organization_id)


def generate_sales(count: int = 100, organization_id: Optional[str] = None) -> List[Dict]:
    """Generate sales data"""
    return DataFactory.generate_batch(DataType.SALES, count, organization_id)
