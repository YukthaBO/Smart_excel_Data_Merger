from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse

import pandas as pd
import io
import json


app = FastAPI()


# Static folder
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# HTML templates
templates = Jinja2Templates(
    directory="templates"
)


# Store uploaded Excel files temporarily
uploaded_files = {}


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.get("/")
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request
        }
    )


# --------------------------------------------------
# ANALYZE EXCEL FILES
# --------------------------------------------------

@app.post("/analyze")
async def analyze_files(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):

    data1 = await file1.read()
    data2 = await file2.read()

    # Read Excel files
    df1 = pd.read_excel(
        io.BytesIO(data1)
    )

    df2 = pd.read_excel(
        io.BytesIO(data2)
    )

    # Save files temporarily
    uploaded_files["file1"] = data1
    uploaded_files["file2"] = data2

    return {
        "file1": file1.filename,
        "file2": file2.filename,

        "file1_columns":
            list(df1.columns),

        "file2_columns":
            list(df2.columns),

        "file1_rows":
            len(df1),

        "file2_rows":
            len(df2)
    }


# --------------------------------------------------
# CREATE MERGED DATAFRAME
# --------------------------------------------------

def create_merged_dataframe(
    matching_columns
):

    # Read uploaded files again
    df1 = pd.read_excel(
        io.BytesIO(
            uploaded_files["file1"]
        )
    )

    df2 = pd.read_excel(
        io.BytesIO(
            uploaded_files["file2"]
        )
    )

    # Matching columns from File 1
    left_columns = [
        match["file1_column"]
        for match in matching_columns
    ]

    # Matching columns from File 2
    right_columns = [
        match["file2_column"]
        for match in matching_columns
    ]

    # Merge
    merged_df = pd.merge(
        df1,
        df2,
        left_on=left_columns,
        right_on=right_columns,
        how="left",
        suffixes=("", "_file2")
    )

    # Remove duplicate matching columns
    for column in right_columns:

        if column in df1.columns:

            duplicate_column = (
                column + "_file2"
            )

            if duplicate_column in merged_df.columns:

                merged_df.drop(
                    columns=[duplicate_column],
                    inplace=True
                )

    return merged_df


# --------------------------------------------------
# MERGE PREVIEW
# --------------------------------------------------

@app.post("/merge")
async def merge_files(
    matches: str = Form(...)
):

    matching_columns = json.loads(
        matches
    )

    # Create merged dataframe
    merged_df = create_merged_dataframe(
        matching_columns
    )

    # First 20 rows for preview
    preview_df = merged_df

    return {
        "rows":
            len(merged_df),

        "columns":
            list(merged_df.columns),

        "preview":
            preview_df.fillna("").to_dict(
                orient="records"
            )
    }


# --------------------------------------------------
# DOWNLOAD MERGED EXCEL
# --------------------------------------------------

@app.post("/download")
async def download_file(
    matches: str = Form(...)
):

    matching_columns = json.loads(
        matches
    )

    # Create final merged dataframe
    merged_df = create_merged_dataframe(
        matching_columns
    )

    # Create Excel file in memory
    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        merged_df.to_excel(
            writer,
            index=False,
            sheet_name="Merged Data"
        )

    output.seek(0)

    # Send Excel file to browser
    return StreamingResponse(
        output,
        media_type=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition":
            "attachment; "
            "filename=merged_excel_data.xlsx"
        }
    )