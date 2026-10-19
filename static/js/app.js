// Tiện ích giao diện nhỏ (không chứa logic phân quyền; mọi quyền được kiểm tra ở máy chủ).
(function () {
  "use strict";
  // Xác nhận trước khi thực hiện thao tác quan trọng: <form data-confirm="...">
  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) { e.preventDefault(); }
  });
  // Mở/đóng sidebar quản trị trên điện thoại
  var toggle = document.getElementById("sidebarToggle");
  var sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("show");
      toggle.setAttribute("aria-expanded", sidebar.classList.contains("show") ? "true" : "false");
    });
  }
  // Tự động gửi form lọc khi đổi lựa chọn
  document.querySelectorAll("form.js-autofilter select").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });
  // Đếm số ảnh đã chọn
  document.querySelectorAll("input[type=file][multiple]").forEach(function (input) {
    input.addEventListener("change", function () {
      var out = document.getElementById(input.id + "_count");
      if (out) { out.textContent = input.files.length ? input.files.length + " tệp đã chọn" : ""; }
    });
  });
})();
