from starlette.middleware.sessions import SessionMiddleware
from uuid import uuid4
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI, Request, Body, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from datetime import datetime

from bson import ObjectId
from models import User, Token
from auth import (
    authenticate_user, 
    create_access_token, 
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from datetime import timedelta, datetime
from database import db
import uvicorn
from embeddings import VectorDB
import logging
from jose import JWTError, jwt
from typing import Optional
from fastapi import UploadFile, File, Form
from rag import RAGSystem
from config import Config
import os

# Initialize RAG system
vector_db = VectorDB()  # <-- Create VectorDB instance
rag_system = RAGSystem(vector_db)  # <-- Pass to RAGSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# JWT Configuration
SECRET_KEY = "your-secret-key-here"  # Replace with a strong secret key
app.add_middleware(SessionMiddleware, secret_key="your-secret-session-key")

ALGORITHM = "HS256"

def decode_and_validate_token(token: str) -> Optional[User]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        
        # Get user from database
        user_data = db.users.find_one({"username": username})
        if not user_data:
            return None
            
        return User(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data.get("password", ""),
            disabled=user_data.get("disabled", False)
        )
    except JWTError:
        return None

async def get_current_active_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )
    # Remove "Bearer " prefix if present
    token = token.replace("Bearer ", "")
    user = decode_and_validate_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )
    return user

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_user(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    email = form_data.get("email")
    password = form_data.get("password")
    
    # Check if user exists
    if db.users.find_one({"username": username}):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Username already registered"
        })
    
    if db.users.find_one({"email": email}):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Email already registered"
        })
    
    # Create new user
    hashed_password = get_password_hash(password)
    user_data = {
        "username": username,
        "email": email,
        "password": hashed_password,
        "disabled": False,
        "created_at": datetime.now()
    }
    
    db.users.insert_one(user_data)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_user(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    
    user = authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Incorrect username or password"
        })
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: User = Depends(get_current_active_user)):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": current_user.username,
        "email": current_user.email
    })

# @app.exception_handler(StarletteHTTPException)
# async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
#     if exc.status_code == status.HTTP_401_UNAUTHORIZED:
#         return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
#     return await request.app.default_exception_handler(request, exc)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # Render 404.html when 401 error occurs
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    
    # For other HTTP errors, return default JSON
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# Handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Generic exception handler
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, current_user: User = Depends(get_current_active_user)):
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "username": current_user.username
    })

@app.post("/upload")
async def upload_document(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Validate file type
        allowed_extensions = {'.txt', '.pdf', '.docx', '.md'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return templates.TemplateResponse("upload.html", {
                "request": request,
                "username": current_user.username,
                "error": "Unsupported file type. Please upload .txt, .pdf, .docx or .md files."
            })
        
        contents = await file.read()
        
        # For text files
        if file_ext == '.txt':
            text = contents.decode("utf-8")
        else:
            text = contents.decode("utf-8", errors="ignore")  # Fallback for other file types
        
        # Store in MongoDB
        document_data = {
            "title": title,
            "description": description,
            "filename": file.filename,
            "filetype": file_ext,
            "uploaded_by": current_user.username,
            "content": text,
            "upload_date": datetime.now()
        }
        
        doc_id = db.documents.insert_one(document_data).inserted_id
        
        # Add to vector store
        rag_system.ingest_document(str(doc_id), text, {
            "title": title,
            "uploaded_by": current_user.username,
            "filetype": file_ext
        })
        
        return RedirectResponse(url="/documents", status_code=303)
    
    except Exception as e:
        return RedirectResponse(url="/documents", status_code=303)
        
        print(f"Exception: {e}")
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "username": current_user.username,
            "error": f"Error uploading file: {str(e)}"
        })

@app.get("/documents", response_class=HTMLResponse)
async def list_documents(request: Request, current_user: User = Depends(get_current_active_user)):
    documents = list(db.documents.find({"uploaded_by": current_user.username}).sort("upload_date", -1))
    
    # Convert ObjectId to string and format date
    for doc in documents:
        doc["_id"] = str(doc["_id"])
        # doc["upload_date"] = doc["upload_date"].strftime("%Y-%m-%d %H:%M")
    
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "documents": documents,
        "username": current_user.username
    })
    
@app.post("/select-document")
async def select_document(
    request: Request,
    document_id: str = Form(...),
    current_user: User = Depends(get_current_active_user)
):
    # Store selected document ID in session/cookie
    # print("document_id: ",document_id)
    response = RedirectResponse(url="/query", status_code=303)
    response.set_cookie(key="selected_document", value=document_id, httponly=True)
    print("response: ",response)
    return response


@app.get("/query", response_class=HTMLResponse)
async def query_page(request: Request, current_user: User = Depends(get_current_active_user)):
    document_id = request.cookies.get("selected_document")
    csrf_token = str(uuid4())

    request.session["csrf_token"] = csrf_token
    if not document_id:
        return templates.TemplateResponse("query.html", {
            "request": request,
            "username": current_user.username,
            "selected_document": None
        })
    
    # Get document from database
    document = db.documents.find_one({"_id": ObjectId(document_id)})
    
    if not document:
        return templates.TemplateResponse("query.html", {
            "request": request,
            "username": current_user.username,
            "selected_document": None,
            "error": "Document not found"
        })
    
    # Handle upload_date formatting
    upload_date_str = str(document.get("upload_date", ""))
    if upload_date_str:
        try:
            upload_date = datetime.strptime(upload_date_str, "%Y-%m-%d %H:%M:%S")
            formatted_date = upload_date.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            formatted_date = upload_date_str
    else:
        formatted_date = ""
    
    return templates.TemplateResponse("query.html", {
        "request": request,
        "username": current_user.username,
        "csrf_token": csrf_token,
        "selected_document": {
            "id": str(document["_id"]),
            "filename": document.get("filename", "Untitled"),
            "upload_date": formatted_date
        }
    })
    
@app.post("/query")
async def process_query(
    request: Request,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Verify CSRF token
        csrf_token = data.get("csrf_token")
        
        if not csrf_token:
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

        query = data.get("query", "").strip()
        document_id = data.get("document_id")
        print("document_id: ", document_id, "query: ", query)
        logger.info(f"Received query - Document ID: {document_id}, Query: {query}")
        
        # Input validation
        if not query or len(query) > 1000:
            raise HTTPException(status_code=400, detail="Query must be between 1 and 1000 characters")
            
        if not document_id or not ObjectId.is_valid(document_id):
            raise HTTPException(
                status_code=400, 
                detail="Invalid document ID. Please select a document first."
            )
            
        # Verify document belongs to user
        document = db.documents.find_one({
            "_id": ObjectId(document_id),
            "uploaded_by": current_user.username
        })
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found or not owned by user")
            
        logger.info(f"Processing query from user {current_user.username} on document {document_id}")
        
        # Process the query
        docs = rag_system.search_documents(query, k=5, document_ids=[document_id])
        
        print("docs: ", docs)
        print("🔢 Total vectors in FAISS index:", vector_db.index.ntotal)
        print("🗺️ FAISS ID to Document Mapping:", vector_db.id_to_doc)

        if not docs:
            return JSONResponse(
                status_code=200,
                content={"warning": "No relevant content found in the selected document"}
            )
        
        response = rag_system.generate_response(query, docs)
        print("response in main: ", response)
        
        # Handle both dict and object formats for documents
        sources = []
        for doc in docs:
            if isinstance(doc, dict):
                # If doc is a dictionary, access content differently
                content = doc.get('page_content', doc.get('text', ''))
                title = doc.get('metadata', {}).get('title', 'Document')
            else:
                # If doc is an object with attributes
                content = getattr(doc, 'page_content', getattr(doc, 'text', ''))
                title = getattr(doc, 'metadata', {}).get('title', 'Document')
            
            sources.append({
                "title": title,
                "content": content[:200] + "..." if len(content) > 200 else content
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "response": response,
                "sources": sources
            }
        )
        
    except HTTPException as he:
        logger.warning(f"HTTPException: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
# def verify_csrf_token(request: Request, token: str) -> bool:
#     """
#     Verify the CSRF token against the one stored in the session
#     """
#     session_token = request.session.get("csrf_token")
#     if not session_token or session_token != token:
#         return False
#     return True


@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

@app.get("/health-view",response_class=HTMLResponse)
async def health_check_view(request: Request,current_user: User = Depends(get_current_active_user)):
    data = await health_check()  # get the data from the same function
    return templates.TemplateResponse("health.html", {
        "request": request,
        "status": data["status"],
        "database": data["database"],
        "email": current_user.email,
        "username": current_user.username,
    })

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)