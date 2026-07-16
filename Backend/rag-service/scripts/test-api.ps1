param(
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Invoke-ChatSession {
    param(
        [string]$Message,
        [int]$TopK = 4
    )

    $body = @{
        message = $Message
        top_k   = $TopK
    } | ConvertTo-Json -Compress -Depth 5

    $client = [System.Net.Http.HttpClient]::new()
    try {
        $content = [System.Net.Http.StringContent]::new(
            $body,
            [System.Text.Encoding]::UTF8,
            "application/json"
        )
        $response = $client.PostAsync("$BaseUrl/chat/session", $content).Result
        $response.EnsureSuccessStatusCode() | Out-Null
        $response.Content.ReadAsStringAsync().Result | ConvertFrom-Json
    }
    finally {
        $client.Dispose()
    }
}

Write-Host "== Test 1: hỏi thuốc trên web ==" -ForegroundColor Cyan
$drug = Invoke-ChatSession -Message "Metformin uống lúc nào tốt nhất?"
$drug | ConvertTo-Json -Depth 6

Write-Host "`n== Test 2: hỏi tài liệu có sẵn ==" -ForegroundColor Cyan
$doc = Invoke-ChatSession -Message "HbA1c bao nhiêu là cần điều trị?"
$doc | ConvertTo-Json -Depth 6

Write-Host "`n== Test 3: lưu tri thức người dùng ==" -ForegroundColor Cyan
$memory = Invoke-ChatSession -Message "/nho bệnh nhân có tiền sử dị ứng penicillin"
$memory | ConvertTo-Json -Depth 6
