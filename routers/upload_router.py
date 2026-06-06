import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pypdf import PdfReader
from starlette import status

from database import db_dependency
from rag import split_text
from rate_limit import upload_rate_limit
from routers.auth_router import user_dependency
from tablebase import DocumentChunks

router = APIRouter(
    prefix="/upload",
    tags=["upload"]
)

logger = logging.getLogger(__name__)


@router.post(
    "/upload_document",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(upload_rate_limit)],
)
async def upload_document(
    user: user_dependency,
    db: db_dependency,
    pdfs: list[UploadFile] = File(...),
):
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not authenticated"
        )

    if len(pdfs) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 fichiers PDF",
        )

    user_id = user.get("id")

    for pdf in pdfs:
        if pdf.content_type and pdf.content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail="Seuls les fichiers PDF sont acceptes",
            )

        if not pdf.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Le fichier doit avoir l'extension .pdf",
            )

        content = await pdf.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="PDF trop volumineux",
            )

        temp_file_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            reader = PdfReader(temp_file_path)
            chunks_to_save = []

            for page_index, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                for chunk in split_text(page_text):
                    chunks_to_save.append(
                        DocumentChunks(
                            user_id=user_id,
                            filename=pdf.filename,
                            page=page_index,
                            content=chunk,
                        )
                    )

            if not chunks_to_save:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Aucun texte lisible trouve dans le PDF",
                )

            db.add_all(chunks_to_save)
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to process uploaded PDF: %s", pdf.filename)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors du traitement du PDF",
            ) from exc
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    return {"message": "Documents ajoutes avec succes"}
