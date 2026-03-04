# 1. Create a custom validation middleware using Starlette
class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 2. Extract API key header (case-insensitive)
        api_key = request.headers.get("x-api-key")

        # 3. Verify the key (use environment variables in production)
        if api_key != "your-secret-api-key":
            # 4. Return HTTP 401 if verification fails
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: Invalid or missing API Key"},
            )

        # Continue to the tool if valid
        return await call_next(request)
