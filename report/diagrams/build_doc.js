const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  convertInchesToTwip, LevelFormat, PageBreak
} = require("docx");

const FONT = "Times New Roman";

function p(text, opts = {}) {
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
    spacing: { after: 200, line: 360 },
    children: [new TextRun({ text, font: FONT, size: 26, italics: opts.italics || false })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 240 },
    children: [new TextRun({ text, font: FONT, bold: true, size: 32, allCaps: true })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 200 },
    children: [new TextRun({ text, font: FONT, bold: true, size: 28 })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 240, after: 160 },
    children: [new TextRun({ text, font: FONT, bold: true, size: 26, italics: true })],
  });
}

const children = [];

// ===================== LÝ DO CHỌN ĐỀ TÀI =====================
children.push(h1("Lý do chọn đề tài"));

children.push(p(
  "Đái tháo đường (tiểu đường) hiện là một trong những bệnh mạn tính không lây phổ biến nhất trên thế giới và đang gia tăng nhanh chóng. Theo số liệu của Liên đoàn Đái tháo đường Thế giới (IDF), năm 2021 toàn cầu có khoảng 537 triệu người trưởng thành mắc bệnh, dự báo con số này sẽ tăng lên khoảng 643 triệu vào năm 2030 và 783 triệu vào năm 2045. Tại Việt Nam, số người mắc đái tháo đường hiện được ước tính vào khoảng 7 triệu người, tỉ lệ mắc bệnh đã tăng gấp đôi so với một thập kỷ trước, trong khi hơn 60% trường hợp chưa được chẩn đoán và trên 55% người bệnh đã có biến chứng về tim mạch, mắt, thần kinh hoặc thận. Đây là gánh nặng rất lớn cho hệ thống y tế cũng như cho chính người bệnh và gia đình."
));

children.push(p(
  "Đái tháo đường là bệnh lý đòi hỏi người bệnh phải tự theo dõi và kiểm soát trong suốt quá trình sống chung với bệnh: đo đường huyết định kỳ, tuân thủ chế độ dinh dưỡng phù hợp với thể trạng và loại bệnh, duy trì vận động, dùng thuốc đúng liều và phát hiện sớm các dấu hiệu bất thường để tránh biến chứng nguy hiểm. Trên thực tế, phần lớn người bệnh tại Việt Nam vẫn quản lý các chỉ số này theo cách thủ công bằng sổ tay hoặc trí nhớ cá nhân, không có công cụ hỗ trợ phân tích xu hướng, không được tư vấn dinh dưỡng cá nhân hóa theo từng thể bệnh (type 1, type 2, tiểu đường thai kỳ, có biến chứng...), và khó tiếp cận tư vấn chuyên môn kịp thời khi xuất hiện tình huống khẩn cấp như hạ đường huyết."
));

children.push(p(
  "Trong khi đó, sự phát triển của trí tuệ nhân tạo và kiến trúc phần mềm hiện đại đã mở ra khả năng xây dựng những hệ thống hỗ trợ chăm sóc sức khỏe thông minh, có thể học máy để dự đoán sớm nguy cơ, dùng thị giác máy tính để đọc kết quả đo và nhận diện món ăn, và dùng mô hình ngôn ngữ lớn kết hợp truy hồi tri thức (RAG) để tư vấn tự nhiên, chính xác và có kiểm soát theo tài liệu y khoa đã được thẩm định thay vì trả lời chung chung. Đây chính là hướng tiếp cận mà nhóm mong muốn khai thác: xây dựng một hệ thống có thể đồng hành cùng người bệnh mỗi ngày, chứ không chỉ là công cụ ghi chép chỉ số."
));

children.push(p(
  "Xuất phát từ nhu cầu thực tiễn nêu trên và mong muốn ứng dụng kiến trúc microservice hiện đại cùng các kỹ thuật AI (dự đoán nguy cơ bằng mô hình học máy, OCR, chatbot RAG, AI thị giác nhận diện dinh dưỡng từ ảnh) vào một bài toán có ý nghĩa xã hội rõ ràng, nhóm quyết định lựa chọn đề tài “Nghiên cứu xây dựng hệ thống quản lý sức khỏe và dinh dưỡng cho bệnh nhân tiểu đường”. Đề tài vừa cho phép nhóm vận dụng kiến thức đã học về thiết kế hệ thống phân tán, cơ sở dữ liệu, học máy và mô hình ngôn ngữ lớn, vừa hướng tới một sản phẩm có khả năng ứng dụng thực tế, hỗ trợ người bệnh tiểu đường tại Việt Nam theo dõi sức khỏe chủ động, ăn uống hợp lý hơn và giảm thiểu nguy cơ biến chứng."
));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ===================== CHƯƠNG 1 =====================
children.push(h1("Chương 1: Đặt vấn đề - Giới thiệu bài toán"));

children.push(h2("1.1. Nhu cầu quản lý sức khỏe và dinh dưỡng cho bệnh nhân tiểu đường"));
children.push(p(
  "Khác với nhiều bệnh lý cấp tính, đái tháo đường là bệnh mạn tính đòi hỏi quá trình theo dõi và can thiệp liên tục, kéo dài suốt đời. Người bệnh cần thực hiện đồng thời nhiều việc: đo và ghi nhận chỉ số đường huyết theo từng thời điểm trong ngày, kiểm soát khẩu phần ăn theo chỉ số đường huyết thực phẩm (GI/GL) và tổng lượng carbohydrate nạp vào, duy trì vận động thể chất, tuân thủ phác đồ thuốc, đồng thời theo dõi các chỉ số liên quan như huyết áp, cân nặng, mỡ máu để phát hiện sớm nguy cơ biến chứng tim mạch, đột quỵ hay suy thận."
));
children.push(p(
  "Việc quản lý thủ công bằng sổ tay hoặc ứng dụng ghi chép đơn thuần bộc lộ nhiều hạn chế: dữ liệu rời rạc, khó tổng hợp thành xu hướng dài hạn; thiếu gợi ý dinh dưỡng phù hợp với thể trạng, loại bệnh và biến chứng cụ thể của từng người; không có cơ chế cảnh báo chủ động khi chỉ số bất thường; và người bệnh khó tiếp cận tư vấn chuyên môn ngay khi cần, đặc biệt trong các tình huống khẩn cấp như hạ đường huyết. Đây chính là khoảng trống mà một hệ thống phần mềm tích hợp có thể giải quyết, thông qua việc số hóa toàn bộ hồ sơ sức khỏe, tự động hóa việc tính toán và cảnh báo, đồng thời cá nhân hóa gợi ý dinh dưỡng dựa trên dữ liệu thực tế của từng người dùng."
));

children.push(h2("1.2. Các hệ thống liên quan và khả năng đáp ứng nhu cầu"));

children.push(h3("1.2.1. Các ứng dụng, hệ thống hiện có"));
children.push(p(
  "Trên thế giới đã có một số ứng dụng hỗ trợ người bệnh tiểu đường được sử dụng rộng rãi, tiêu biểu như mySugr và Glucose Buddy. Các ứng dụng này cho phép người dùng ghi nhận đường huyết, liều thuốc và bữa ăn trong cùng một lượt nhập liệu, theo dõi xu hướng đường huyết, cân nặng, huyết áp và chỉ số A1C theo thời gian, đồng thời xuất báo cáo dạng PDF/CSV để chia sẻ với bác sĩ. Một số ứng dụng còn hỗ trợ đồng bộ với máy đo đường huyết qua Bluetooth và tích hợp với nền tảng sức khỏe của hệ điều hành."
));
children.push(p(
  "Tuy nhiên, các ứng dụng này chủ yếu tập trung vào việc ghi chép và trực quan hóa chỉ số, chưa khai thác sâu các kỹ thuật AI để dự đoán nguy cơ đa bệnh (tim mạch, đột quỵ) dựa trên hồ sơ sức khỏe tổng thể. Cơ sở dữ liệu món ăn thường xây dựng theo khẩu phần ăn phương Tây, không phù hợp với thói quen ẩm thực Việt Nam. Phần lớn không có chatbot tư vấn bằng tiếng Việt dựa trên tài liệu y khoa được kiểm soát nội dung, không hỗ trợ nhận diện món ăn qua ảnh chụp bữa ăn thực tế, và nhiều tính năng nâng cao chỉ mở khóa khi trả phí. Tại Việt Nam, một số nền tảng sức khỏe tổng quát đã xuất hiện nhưng phần lớn chưa chuyên biệt hóa sâu cho bài toán tiểu đường theo hướng kết hợp đồng thời hồ sơ sức khỏe, dự đoán nguy cơ, dinh dưỡng cá nhân hóa và tư vấn AI trong cùng một hệ thống."
));

children.push(h3("1.2.2. Khoảng trống và sự cần thiết xây dựng hệ thống mới"));
children.push(p(
  "Từ việc khảo sát các hệ thống liên quan, có thể thấy rõ ba khoảng trống chính. Thứ nhất là khoảng trống về tích hợp: các giải pháp hiện tại thường chỉ giải quyết một phần của bài toán (hoặc ghi chép chỉ số, hoặc gợi ý dinh dưỡng, hoặc tư vấn), trong khi người bệnh cần một hệ thống đồng bộ theo dõi hồ sơ sức khỏe, dinh dưỡng, cảnh báo và tư vấn xuyên suốt. Thứ hai là khoảng trống về bản địa hóa: thiếu hệ thống nhận diện món ăn Việt Nam qua hình ảnh và thiếu công cụ OCR đọc kết quả từ các thiết bị đo tại nhà hoặc phiếu xét nghiệm theo định dạng phổ biến ở Việt Nam. Thứ ba là khoảng trống về phản ứng chủ động: thiếu cơ chế phát hiện tình huống khẩn cấp từ nhật ký sức khỏe hoặc hội thoại chatbot để tự động cảnh báo và gửi thông báo kịp thời."
));
children.push(p(
  "Những khoảng trống này là cơ sở để nhóm xây dựng hệ thống HealthCare Diabetes theo hướng tích hợp đầy đủ các module: quản lý tài khoản và hồ sơ sức khỏe, dự đoán nguy cơ tiểu đường/tim mạch/đột quỵ bằng mô hình học máy, OCR ảnh máy đo và tài liệu xét nghiệm, gợi ý và lập kế hoạch dinh dưỡng theo thể bệnh, nhận diện dinh dưỡng từ ảnh bữa ăn bằng AI thị giác, chatbot tư vấn kiến thức tiểu đường theo kỹ thuật RAG, cùng cơ chế nhắc nhở và cảnh báo sức khỏe liên thông qua thông báo và email."
));

children.push(h2("1.3. Tổng quan về công nghệ AI ứng dụng trong quản lý bệnh mạn tính"));
children.push(p(
  "Việc ứng dụng trí tuệ nhân tạo trong chăm sóc sức khỏe mạn tính hiện xoay quanh bốn nhóm kỹ thuật chính, đều được khai thác trong hệ thống của nhóm. Nhóm thứ nhất là mô hình học máy có giám sát (như hồi quy logistic, cây quyết định, ensemble learning) được huấn luyện trên các đặc trưng lâm sàng (tuổi, giới tính, BMI, đường huyết, insulin, cholesterol, huyết áp...) để sàng lọc sớm nguy cơ mắc bệnh, hỗ trợ chứ không thay thế chẩn đoán y khoa chính thức. Nhóm thứ hai là công nghệ nhận dạng ký tự quang học (OCR) kết hợp thị giác máy tính, giúp số hóa kết quả từ màn hình máy đo đường huyết/huyết áp và tài liệu xét nghiệm giấy, giảm sai sót khi nhập liệu thủ công."
));
children.push(p(
  "Nhóm thứ ba là mô hình ngôn ngữ lớn (LLM) kết hợp kỹ thuật truy hồi tăng cường sinh (Retrieval-Augmented Generation - RAG), cho phép chatbot trả lời câu hỏi về tiểu đường dựa trên tài liệu y khoa đã được lập chỉ mục trong cơ sở dữ liệu vector, thay vì chỉ dựa vào kiến thức nội tại của mô hình, qua đó tăng độ tin cậy và khả năng kiểm soát nội dung y tế nhạy cảm. Nhóm thứ tư là AI thị giác đa phương thức (multimodal vision) dùng để nhận diện món ăn và ước lượng thành phần dinh dưỡng trực tiếp từ ảnh chụp bữa ăn, giúp người dùng ghi nhận khẩu phần ăn một cách nhanh chóng và tự nhiên hơn so với nhập liệu thủ công. Xu hướng chung là kết hợp các kỹ thuật này trong một kiến trúc microservice để mỗi module AI có thể phát triển, mở rộng và bảo trì độc lập."
));

children.push(h2("1.4. Kết luận"));
children.push(p(
  "Chương 1 đã trình bày bối cảnh và động lực cho việc xây dựng hệ thống quản lý sức khỏe và dinh dưỡng cho bệnh nhân tiểu đường. Gánh nặng bệnh tật ngày càng tăng tại Việt Nam và trên thế giới, cùng với những hạn chế của phương pháp quản lý thủ công và khoảng trống của các ứng dụng hiện có, cho thấy sự cần thiết của một hệ thống tích hợp, có khả năng theo dõi sức khỏe, cá nhân hóa dinh dưỡng và tư vấn chủ động bằng AI. Đây là cơ sở để nhóm đề xuất xây dựng hệ thống HealthCare Diabetes, kết hợp kiến trúc microservice hiện đại với các kỹ thuật học máy, OCR, RAG và AI thị giác, được trình bày chi tiết trong các chương tiếp theo."
));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ===================== CHƯƠNG 2 =====================
children.push(h1("Chương 2: Cơ sở lý thuyết"));

children.push(h2("2.1. Kiến trúc Microservices"));
children.push(p(
  "Microservices là kiến trúc phần mềm trong đó một hệ thống lớn được chia thành tập hợp các dịch vụ nhỏ, độc lập, mỗi dịch vụ đảm nhận một nghiệp vụ cụ thể và có thể được phát triển, triển khai, mở rộng riêng biệt. Các dịch vụ giao tiếp với nhau qua giao thức mạng (thường là REST/HTTP hoặc message queue) và thường được đăng ký, khám phá lẫn nhau thông qua một service registry. So với kiến trúc nguyên khối (monolithic), microservices giúp tăng khả năng mở rộng theo từng thành phần, cô lập lỗi tốt hơn và cho phép nhiều đội phát triển làm việc song song trên các công nghệ khác nhau, nhưng đổi lại đòi hỏi cơ chế điều phối, giám sát và bảo mật giao tiếp nội bộ phức tạp hơn. Hệ thống của nhóm áp dụng kiến trúc này để tách riêng các nghiệp vụ tài khoản, dinh dưỡng, sức khỏe, thông báo và chatbot AI thành các service độc lập, đứng sau một API Gateway duy nhất."
));

children.push(h2("2.2. Spring Boot và Spring Cloud (Gateway, Eureka)"));
children.push(p(
  "Spring Boot là framework xây dựng trên nền Spring Framework của Java, giúp đơn giản hóa việc cấu hình và khởi tạo ứng dụng nhờ cơ chế tự động cấu hình (auto-configuration) và máy chủ nhúng. Tính năng cốt lõi kế thừa từ Spring là Dependency Injection, cho phép các thành phần được khởi tạo và “tiêm” vào nhau một cách linh hoạt, giúp mã nguồn dễ kiểm thử và mở rộng. Spring Cloud Gateway đóng vai trò cổng vào duy nhất (API Gateway) của hệ thống, chịu trách nhiệm định tuyến request tới các microservice nội bộ, xác thực JWT, xử lý CORS và giới hạn tần suất truy cập (rate limit). Netflix Eureka đóng vai trò service registry, cho phép các service Java tự đăng ký tên dịch vụ khi khởi động, nhờ đó Gateway có thể định tuyến động theo tên logic của service thay vì địa chỉ IP cố định, thuận lợi khi triển khai và mở rộng bằng container."
));

children.push(h2("2.3. ReactJS và hệ sinh thái frontend"));
children.push(p(
  "ReactJS là thư viện JavaScript mã nguồn mở do Meta phát triển, dùng để xây dựng giao diện người dùng theo mô hình component hóa: giao diện được chia thành các thành phần độc lập, có thể tái sử dụng và tự quản lý trạng thái, giúp tối ưu hiệu năng render thông qua Virtual DOM. Kết hợp với TypeScript, React giúp phát hiện lỗi kiểu dữ liệu ngay khi biên dịch, tăng độ an toàn cho mã nguồn ở quy mô lớn. Vite được sử dụng làm công cụ build và dev server nhờ tốc độ khởi động và hot-reload nhanh so với các bundler truyền thống. Các thư viện bổ trợ như React Router (điều hướng và bảo vệ route theo vai trò người dùng), react-hook-form kết hợp zod (quản lý và kiểm tra dữ liệu biểu mẫu), cùng Axios (giao tiếp API, tự động gắn access token và làm mới token khi hết hạn) tạo thành nền tảng frontend hoàn chỉnh cho hệ thống."
));

children.push(h2("2.4. Django REST Framework và FastAPI"));
children.push(p(
  "Bên cạnh các service viết bằng Java, hệ thống còn sử dụng Python cho các nghiệp vụ liên quan nhiều đến xử lý dữ liệu và AI. Django REST Framework (DRF) là bộ công cụ mở rộng của Django chuyên dùng để xây dựng RESTful API, cung cấp sẵn cơ chế serializer để chuyển đổi giữa model cơ sở dữ liệu và JSON, cùng hệ thống xác thực, phân quyền và ORM mạnh mẽ, phù hợp cho các nghiệp vụ phức tạp như quản lý hồ sơ sức khỏe, xét nghiệm và báo cáo. FastAPI là framework Python hiện đại, xây dựng trên chuẩn ASGI, nổi bật với hiệu năng cao, hỗ trợ bất đồng bộ (async) và tự sinh tài liệu API (OpenAPI/Swagger) từ type hint, do đó phù hợp để triển khai các service cần độ trễ thấp như API phục vụ mô hình dự đoán học máy."
));

children.push(h2("2.5. Hệ quản trị cơ sở dữ liệu PostgreSQL"));
children.push(p(
  "PostgreSQL là hệ quản trị cơ sở dữ liệu quan hệ mã nguồn mở, tuân thủ chuẩn ACID (Atomicity, Consistency, Isolation, Durability) nhằm đảm bảo tính toàn vẹn và nhất quán của dữ liệu trong các giao dịch. PostgreSQL hỗ trợ tốt các kiểu dữ liệu phức tạp (JSON/JSONB, mảng), transaction đáng tin cậy và khả năng mở rộng thông qua extension, phù hợp làm nền tảng lưu trữ cho dữ liệu nghiệp vụ quan trọng như hồ sơ sức khỏe, kết quả xét nghiệm và giao dịch người dùng. Trong hệ thống, mỗi microservice sở hữu schema dữ liệu riêng theo nguyên tắc database-per-service, giúp giảm sự phụ thuộc chéo giữa các service và cho phép thay đổi mô hình dữ liệu của một service mà không ảnh hưởng tới các service còn lại."
));

children.push(h2("2.6. Redis"));
children.push(p(
  "Redis là hệ thống lưu trữ dữ liệu trong bộ nhớ (in-memory data store) dạng key-value, có tốc độ đọc/ghi rất cao nên thường được dùng làm lớp cache, quản lý session hoặc hàng đợi tác vụ nhẹ. Trong hệ thống, Redis được sử dụng cho nhiều mục đích: lưu lịch sử hội thoại và trạng thái phiên chat của chatbot RAG, cache kết quả truy vấn để giảm tải cho các service backend, hỗ trợ cơ chế rate limit tại API Gateway, và làm hàng đợi trung gian để worker xử lý bất đồng bộ các tác vụ như phân tích ảnh bữa ăn bằng AI Vision."
));

children.push(h2("2.7. Cơ sở dữ liệu vector Qdrant và kỹ thuật RAG"));
children.push(p(
  "Qdrant là cơ sở dữ liệu vector mã nguồn mở, chuyên dùng để lưu trữ và tìm kiếm các vector embedding theo độ tương đồng ngữ nghĩa (semantic similarity search), thay vì tìm kiếm theo từ khóa chính xác như cơ sở dữ liệu quan hệ truyền thống. Đây là thành phần nền tảng cho kỹ thuật Retrieval-Augmented Generation (RAG): tài liệu y khoa được chia thành các đoạn nhỏ (chunk), chuyển thành vector bằng mô hình embedding đa ngôn ngữ (sentence-transformers), sau đó lưu vào Qdrant. Khi người dùng đặt câu hỏi, hệ thống truy vấn Qdrant để lấy ra những đoạn tài liệu liên quan nhất, đưa vào ngữ cảnh của prompt trước khi gửi cho mô hình ngôn ngữ lớn sinh câu trả lời. Cách tiếp cận này giúp câu trả lời của chatbot bám sát tài liệu y khoa đã được kiểm soát, giảm hiện tượng “ảo giác” (hallucination) so với việc chỉ dựa vào kiến thức nội tại của mô hình."
));

children.push(h2("2.8. Học máy trong dự đoán nguy cơ bệnh mạn tính"));
children.push(p(
  "Học máy có giám sát (supervised learning) là nhánh của trí tuệ nhân tạo trong đó mô hình được huấn luyện trên tập dữ liệu có nhãn để học quy luật ánh xạ từ đặc trưng đầu vào sang kết quả dự đoán. Trong bài toán sàng lọc nguy cơ bệnh mạn tính, các đặc trưng lâm sàng như tuổi, giới tính, chỉ số khối cơ thể (BMI), đường huyết, insulin, cholesterol và huyết áp được đưa vào mô hình đã huấn luyện (lưu dưới dạng artifact `.pkl` bằng thư viện scikit-learn/joblib) để tính xác suất nguy cơ mắc tiểu đường, bệnh tim mạch hoặc đột quỵ. Kết quả dự đoán mang tính chất ước tính thống kê, hỗ trợ sàng lọc và cảnh báo sớm, không thay thế chẩn đoán lâm sàng của bác sĩ chuyên khoa."
));

children.push(h2("2.9. Công nghệ nhận dạng ký tự quang học (OCR)"));
children.push(p(
  "OCR (Optical Character Recognition) là công nghệ chuyển đổi văn bản trong hình ảnh thành dữ liệu văn bản có thể xử lý được. Google Vision API là dịch vụ OCR dựa trên đám mây, có khả năng nhận diện văn bản in, viết tay và bố cục tài liệu phức tạp với độ chính xác cao, được sử dụng để trích xuất kết quả từ ảnh chụp tài liệu xét nghiệm. Đối với ảnh chụp màn hình hiển thị dạng số bảy đoạn (seven-segment display) của máy đo đường huyết/huyết áp tại nhà — vốn có đặc thù khác với văn bản in thông thường — hệ thống kết hợp thêm xử lý ảnh cục bộ bằng OpenCV và Pillow để tăng độ chính xác nhận diện chỉ số, từ đó giảm thao tác nhập liệu thủ công cho người bệnh."
));

children.push(h2("2.10. Mô hình ngôn ngữ lớn (LLM) Gemini"));
children.push(p(
  "Mô hình ngôn ngữ lớn (Large Language Model) là mô hình học sâu được huấn luyện trên khối lượng văn bản khổng lồ, có khả năng hiểu và sinh ngôn ngữ tự nhiên cho nhiều tác vụ khác nhau. Gemini là dòng mô hình ngôn ngữ lớn đa phương thức, có khả năng xử lý cả văn bản lẫn hình ảnh trong cùng một truy vấn, được sử dụng trong hệ thống cho hai vai trò chính: sinh câu trả lời tư vấn cho chatbot RAG dựa trên ngữ cảnh truy hồi được từ Qdrant, và phân tích ảnh bữa ăn (Gemini Vision) để nhận diện món ăn cùng ước lượng thành phần dinh dưỡng. Để tăng độ ổn định khi gọi API bên ngoài, hệ thống áp dụng cơ chế key pool (luân chuyển nhiều API key) và fallback model khi gặp lỗi hoặc giới hạn tần suất."
));

children.push(h2("2.11. JWT và bảo mật hệ thống phân tán"));
children.push(p(
  "JSON Web Token (JWT) là chuẩn mở dùng để truyền tải thông tin xác thực giữa các bên dưới dạng một chuỗi JSON được ký số, cho phép server xác minh tính toàn vẹn của token mà không cần lưu trạng thái phiên. Trong hệ thống, JWT được dùng làm access token cho các request từ frontend, kết hợp với refresh token để khôi phục phiên đăng nhập khi access token hết hạn. Ở tầng nội bộ giữa các microservice, API Gateway ký thông tin ngữ cảnh người dùng (`X-User-Context`) bằng cơ chế HMAC trước khi chuyển tiếp tới service phía sau, giúp các service Java/Python xác định được danh tính và vai trò người dùng mà không cần xác thực lại, đồng thời ngăn chặn việc gọi trực tiếp vào service nội bộ mà không qua Gateway."
));

children.push(h2("2.12. Docker và Docker Compose"));
children.push(p(
  "Docker là nền tảng container hóa, cho phép đóng gói ứng dụng cùng toàn bộ môi trường chạy (runtime, thư viện, cấu hình) thành một image thống nhất, đảm bảo ứng dụng chạy nhất quán trên mọi môi trường triển khai. Docker Compose cho phép định nghĩa và khởi chạy nhiều container có liên kết với nhau (cơ sở dữ liệu, cache, các microservice, worker...) chỉ bằng một tệp cấu hình khai báo, quản lý thứ tự phụ thuộc và mạng nội bộ giữa các container. Đây là công cụ phù hợp để triển khai một hệ thống microservices gồm nhiều thành phần như của nhóm, giúp đơn giản hóa việc dựng môi trường phát triển cũng như môi trường production."
));

children.push(h2("2.13. Kết luận"));
children.push(p(
  "Chương 2 đã trình bày cơ sở lý thuyết của các công nghệ nền tảng được sử dụng để xây dựng hệ thống: kiến trúc microservices cùng Spring Boot/Spring Cloud cho tầng backend Java, ReactJS cho tầng giao diện, Django REST Framework và FastAPI cho các service Python, PostgreSQL và Redis cho tầng lưu trữ và cache, Qdrant cùng kỹ thuật RAG cho chatbot tư vấn, học máy cho dự đoán nguy cơ, OCR cho số hóa dữ liệu y tế, mô hình ngôn ngữ lớn Gemini cho các tác vụ AI ngôn ngữ và thị giác, cùng JWT và Docker cho bảo mật và triển khai hệ thống. Đây là nền tảng lý thuyết để nhóm tiến hành phân tích yêu cầu và thiết kế chi tiết hệ thống ở các chương tiếp theo."
));

const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1418, bottom: 1134, left: 1701, right: 1134 },
        },
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("/home/claude/Bao_cao_LyDo_Chuong1_Chuong2.docx", buf);
  console.log("done");
});
