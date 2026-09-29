from fastapi import APIRouter
from fastapi.responses import Response
from . import performance
from .performance_models import ParseCSV, Preview, Apply, Inclusion

router = APIRouter(prefix="/api/performance")


@router.get("")
def read():
    return performance.service.view()


@router.get("/template")
def template():
    return Response(
        ",".join(performance.HEADERS) + "\n",
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="jdh-performance-template.csv"'
        },
    )


@router.post("/parse")
def parse(data: ParseCSV):
    return {"rows": performance.parse_csv(data.csv)}


@router.post("/preview")
def preview(data: Preview):
    return performance.service.preview(data)


@router.post("/apply")
def apply(data: Apply):
    return performance.service.apply(data.review_id)


@router.put("/{rid}/inclusion")
def inclusion(rid: str, data: Inclusion):
    return performance.service.inclusion(rid, data)
