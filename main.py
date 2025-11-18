import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utils ---------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception as e:
            raise ValueError("Invalid ObjectId") from e

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if d.get("_id"):
        d["id"] = str(d.pop("_id"))
    # Convert any nested ObjectIds
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
    return d


# --------- Schemas ---------
class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = Field(ge=1)

class OrderCreate(BaseModel):
    name: str
    email: str
    address: str
    items: List[OrderItem]
    notes: Optional[str] = None


# --------- Seed Data ---------
SEED_PRODUCTS = [
    {
        "title": "MoreNutrition Clear Whey – Sugar Free",
        "description": "Refreshing high-protein, sugar‑free clear whey isolate with natural flavors.",
        "price": 29.99,
        "category": "Protein",
        "in_stock": True,
        "image_url": "https://images.unsplash.com/photo-1517677208171-0bc6725a3e60?q=80&w=1200&auto=format&fit=crop",
        "brand": "MoreNutrition",
        "sugar_free": True,
        "tags": ["protein", "sugar-free", "low-calorie"],
    },
    {
        "title": "MoreNutrition Vegan Protein – Chocolate",
        "description": "Plant-based protein blend, sweetened without sugar. Smooth chocolate taste.",
        "price": 24.5,
        "category": "Protein",
        "in_stock": True,
        "image_url": "https://images.unsplash.com/photo-1549575810-45d1344b9b2a?q=80&w=1200&auto=format&fit=crop",
        "brand": "MoreNutrition",
        "sugar_free": True,
        "tags": ["vegan", "protein", "dairy-free"],
    },
    {
        "title": "MoreNutrition Vitamin Gummies – Sugar Free",
        "description": "Daily multivitamin gummies with zero sugar and natural fruit flavors.",
        "price": 14.9,
        "category": "Vitamins",
        "in_stock": True,
        "image_url": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?q=80&w=1200&auto=format&fit=crop",
        "brand": "MoreNutrition",
        "sugar_free": True,
        "tags": ["vitamins", "gummies", "immune"],
    },
    {
        "title": "MoreNutrition Flavor Drops – Sugar Free Vanilla",
        "description": "Calorie‑free flavor drops to sweeten shakes, yogurt, and coffee.",
        "price": 9.99,
        "category": "Flavoring",
        "in_stock": True,
        "image_url": "https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=1200&auto=format&fit=crop",
        "brand": "MoreNutrition",
        "sugar_free": True,
        "tags": ["flavor", "vanilla", "drops"],
    },
    {
        "title": "MoreNutrition Zero Syrup – Chocolate",
        "description": "Rich chocolate syrup with zero sugar – perfect for pancakes or oats.",
        "price": 6.99,
        "category": "Syrups",
        "in_stock": True,
        "image_url": "https://images.unsplash.com/photo-1546549039-98bf4f8c71d1?q=80&w=1200&auto=format&fit=crop",
        "brand": "MoreNutrition",
        "sugar_free": True,
        "tags": ["syrup", "zero", "topping"],
    },
]

@app.on_event("startup")
def seed_products_if_empty():
    if db is None:
        return
    try:
        count = db["product"].count_documents({})
        if count == 0:
            for p in SEED_PRODUCTS:
                create_document("product", p)
    except Exception:
        pass


# --------- Routes ---------
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/api/products")
def list_products(category: Optional[str] = None, search: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    query: Dict[str, Any] = {}
    if category:
        query["category"] = {"$regex": f"^{category}$", "$options": "i"}
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]
    docs = get_documents("product", query)
    return [serialize_doc(d) for d in docs]

@app.get("/api/categories")
def list_categories():
    if db is None:
        return []
    cats = db["product"].distinct("category")
    return sorted([c for c in cats if c])

@app.post("/api/orders")
def create_order(order: OrderCreate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    total = sum(item.price * item.quantity for item in order.items)
    data = order.model_dump()
    data["total"] = round(total, 2)
    order_id = create_document("order", data)
    return {"id": order_id, "total": data["total"], "status": "received"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
