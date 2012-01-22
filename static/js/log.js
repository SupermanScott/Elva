var Elva = (typeof module !== 'undefined' && module.exports) || {};

(function (exports) {
  exports.name = "elva"
  exports.listen = listen;
  exports.messages_per_second = 10;
  exports.buffer_size = 0;
  exports.current_name = false;

  var message_buffer = new Array();
  var listening = false;

  var template = "<tr class='{{name_class}} {{level_class}}' style='display: {{display}};'>" +
                    "<td>{{name}}</td>" +
                    "<td>{{level}}</td>" +
                    "<td><pre>{{msg}}</pre></td>" +
                    "<td>{{filename}} on {{line_no}}</td>" +
                 "</tr>"

  function listen() {
    if (!listening) {
      var source = new EventSource('/events');
      source.addEventListener('message', on_message);
      setInterval(add_messages, 1000);
      listening = true;
    }
  }

  function add_messages() {
    for (i = 0; i < exports.messages_per_second; i++) {
      if (i >= message_buffer.length) {
        break;
      }

      message = message_buffer.shift();

      if (exports.current_name && exports.current_name != message.name) {
        message.display = 'none';
      }

      $('#log-area table').prepend(Mustache.to_html(template, message));
      exports.buffer_size--;
      $('#elva-count').text(exports.buffer_size);
    }
  }

  function on_message(event) {
    message = JSON.parse(event.data)
    message.level_class = message.level.replace('.', '-');
    message.name_class = message.name.replace('.', '-');
    message_buffer.push(message);
    exports.buffer_size++;
    $('#elva-count').text(exports.buffer_size);
  }
})(Elva);