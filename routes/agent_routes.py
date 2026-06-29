from fastapi import APIRouter, Depends
from pydantic import BaseModel
import google.generativeai as genai
from database import SessionLocal
from models import ProductDB, SaleDB
from sqlalchemy.orm import Session
from auth import get_current_user
import json
from sqlalchemy import func
router = APIRouter()

from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-3.1-flash-lite"
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
        sales_summary = {}

        for sale in sales:

            product = db.query(ProductDB).filter(
                ProductDB.id == sale.product_id
            ).first()

            if product:

                sales_summary[product.name] = (
                    sales_summary.get(product.name, 0)
                    + sale.quantity_sold
                )
        top_product = "No sales"

        if sales_summary:

            top_product = max(
                sales_summary,
                key=sales_summary.get
            )
        low_stock = []

        for product in products:

            if product.quantity <= 10:

                low_stock.append(
                    product.name
                )
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
                f"{sale.quantity_sold} sold on"
                f"{sale.sale_date}\n"
            )
        question_text = question.question.lower()
        if "top selling product" in question_text:
            return {
                "message": f"Top selling product is {top_product}"
            }

        if "low stock" in question_text:
            return {
                "message": f"Low stock products: {', '.join(low_stock)}"
            }
        prompt = f"""
You are an AI Inventory Agent.

Your job is to either:
1. Identify an action requested by the user.
2. Answer inventory-related questions.

Possible actions:
- ADD_PRODUCT
- UPDATE_PRODUCT
- DELETE_PRODUCT
- RECORD_SALE
- SHOW_INVENTORY

If the user wants to perform one of the above actions, return ONLY JSON in this format:

{{
    "action": "ADD_PRODUCT",
    "product": "Rice",
    "quantity": 20
}}

For UPDATE_PRODUCT:

{{
    "action": "UPDATE_PRODUCT",
    "product": "Rice",
    "quantity": 100
}}

For DELETE_PRODUCT:

{{
    "action": "DELETE_PRODUCT",
    "product": "Rice",
    "confirm": false
}}
User:
YES DELETE Rice

Response:
{{
    "action":"DELETE_PRODUCT",
    "product":"Rice",
    "confirm":true
}}
For RECORD_SALE:

{{
    "action": "RECORD_SALE",
    "product": "Rice",
    "quantity": 5
}}
For SHOW_INVENTORY:

{{
    "action": "SHOW_INVENTORY"
}}
If the user is only asking a question, then answer normally in plain English.

Rules:
1. Inventory quantities are current stock.
2. Do not subtract sales from inventory.
3. Use inventory data as the source of truth.
4. Use sales data only for sales analysis.
5. Keep answers concise.

Inventory Data:
{inventory_data}

Sales Data:
{sales_data}

Business Insights:

Top Selling Product:
{top_product}

Low Stock Products:
{low_stock}

User Request:
{question.question}
"""

        try:

            response = model.generate_content(prompt)

            try:
                ai_response = json.loads(response.text)
            except:
                return {"message": response.text}

            action = ai_response.get("action")

            if action == "ADD_PRODUCT":
                product_name = ai_response.get("product")
                quantity = ai_response.get("quantity")
                existing_product = db.query(ProductDB).filter(func.lower(ProductDB.name)==product_name.lower()).first()
                if existing_product:
                    existing_product.quantity += quantity
                    db.commit()
                    return {"message": f"<b>Product updated successfully.</b><br><br><b>Product:</b> {product_name}<br><b>Quantity Added:</b> {quantity}<br><b>Current Stock:</b> {existing_product.quantity}"}
                new_product=ProductDB(name=product_name,quantity=quantity)
                db.add(new_product); db.commit()
                return {"message": f"<b>Product added successfully.</b><br><br><b>Product:</b> {product_name}<br><b>Initial Stock:</b> {quantity}"}

            if action=="UPDATE_PRODUCT":
                product_name=ai_response.get("product")
                quantity=ai_response.get("quantity")
                product=db.query(ProductDB).filter(func.lower(ProductDB.name)==product_name.lower()).first()
                if not product:
                    return {"message": f"<b>Product not found.</b><br><br><b>Product:</b> {product_name}"}
                product.quantity=quantity
                db.commit()
                return {"message": f"<b>Product updated successfully.</b><br><br><b>Product:</b> {product_name}<br><b>Current Stock:</b> {quantity}"}

            if action=="RECORD_SALE":
                product_name=ai_response.get("product")
                quantity=int(ai_response.get("quantity"))
                product=db.query(ProductDB).filter(func.lower(ProductDB.name)==product_name.lower()).first()
                if not product:
                    return {"message": f"<b>Product not found.</b><br><br><b>Product:</b> {product_name}"}
                if product.quantity<quantity:
                    return {"message": f"<b>Insufficient stock.</b><br><br><b>Available Stock:</b> {product.quantity}"}
                db.add(SaleDB(product_id=product.id,quantity_sold=quantity))
                product.quantity-=quantity
                db.commit()
                return {"message": f"<b>Sale recorded successfully.</b><br><br><b>Product:</b> {product_name}<br><b>Quantity Sold:</b> {quantity}<br><b>Remaining Stock:</b> {product.quantity}"}
            if action == "SHOW_INVENTORY":

                message = "<b>Current Inventory</b><br><br>"

                for product in products:

                    message += (
                        f"<b>{product.name}</b>: "
                        f"{product.quantity}<br>"
                    )

                return {
                    "message": message
                }
            if action=="DELETE_PRODUCT":
                product_name=ai_response.get("product")
                confirm=ai_response.get("confirm",False)
                product=db.query(ProductDB).filter(func.lower(ProductDB.name)==product_name.lower()).first()
                if not product:
                    return {"message": f"<b>Product not found.</b><br><br><b>Product:</b> {product_name}"}
                if not confirm:
                    return {"message": f"<b>Delete Confirmation Required</b><br><br><b>Product:</b> {product.name}<br><b>Current Stock:</b> {product.quantity}<br><br>Type <b>YES DELETE {product.name}</b> to confirm deletion."}
                db.delete(product); db.commit()
                return {"message": f"<b>Product deleted successfully.</b><br><br><b>Product:</b> {product.name}"}

            return {"message": response.text}

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"message": str(e)}

    finally:
        db.close()
