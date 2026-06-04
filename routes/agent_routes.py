from fastapi import APIRouter, Depends
from pydantic import BaseModel
import google.generativeai as genai
from database import SessionLocal
from models import ProductDB, SaleDB
from sqlalchemy.orm import Session
from auth import get_current_user
router = APIRouter()

import os

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


class AgentQuestion(BaseModel):
    question: str


@router.post("/agent")
def agent(
    question: AgentQuestion,
    current_user: str = Depends(get_current_user)
):

    db: Session = SessionLocal()

    try:

        products = db.query(ProductDB).all()
        sales = db.query(SaleDB).all()
        inventory_data = ""

        for product in products:

            inventory_data += (
                f"{product.name}: "
                f"{product.quantity}\n"
            )

        sales_data = ""

        for sale in sales:

            product = db.query(ProductDB).filter(
                ProductDB.id == sale.product_id
            ).first()

            product_name = (
                product.name
                if product
                else "Deleted Product"
            )

            sales_data += (
                f"{product_name}: "
                f"{sale.quantity_sold} sold\n"
            )

        prompt = f"""
        You are an Inventory Management Assistant.

        Rules:
        1. Inventory quantities are current stock.
        2. Do not subtract sales from inventory.
        3. Use inventory data as the source of truth.
        4. Use sales data only for sales analysis.
        5. If unsure, say information is unavailable.
        6. Keep answers concise.

        Inventory Data:
        {inventory_data}

        Sales Data:
        {sales_data}

        Question:
        {question.question}
        """

        response = model.generate_content(
            prompt
        )

        return {
            "message": response.text
        }

    finally:
        db.close()