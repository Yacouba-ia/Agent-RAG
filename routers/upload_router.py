import logging
import os
import tempfile
from pathlib import Path

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
MAX_UPLOAD_COUNT = 10
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_PDF_CONTENT_TYPE = "application/pdf"


@router.post(
    "/upload_document",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(upload_rate_limit)],
)
async def upload_document(
    user: user_dependency,
    db: db_dependency,
    pdfs: UploadFile = File(...),
):
    """Extrait le texte des PDF, le decoupe en morceaux et stocke les chunks dans PostgreSQL."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non authentifie",
        )

    if len(pdfs) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier PDF fourni",
        )

    if len(pdfs) > MAX_UPLOAD_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 fichiers PDF",
        )

    user_id = user.get("id")

    for pdf in pdfs:
        if not pdf.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier doit avoir un nom valide",
            )

        filename = Path(pdf.filename).name
        if filename != pdf.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le nom du fichier est invalide",
            )

        if pdf.content_type and pdf.content_type != ALLOWED_PDF_CONTENT_TYPE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Seuls les fichiers PDF sont acceptes",
            )

        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier doit avoir l'extension .pdf",
            )

        content = await pdf.read()
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF trop volumineux",
            )

        temp_file_path = None

        try:
            # pypdf a besoin d'un chemin de fichier.
            # Les uploads passent donc par un fichier temporaire.
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
                # Les PDF vides ou scannes sont refuses clairement.
                # On evite ainsi de stocker des lignes inutiles.
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
            logger.exception("Failed to process uploaded PDF: %s", filename)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors du traitement du PDF",
            ) from exc
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                # On supprime toujours le fichier temporaire.
                # Cela reste vrai meme si le parsing ou l'ecriture en base echoue.
                os.remove(temp_file_path)

    return {"message": "Documents ajoutes avec succes"}
