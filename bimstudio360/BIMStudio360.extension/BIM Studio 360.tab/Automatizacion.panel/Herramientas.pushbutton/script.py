# -*- coding: utf-8 -*-
"""Modeless native WPF client. Never block Revit while waiting for its HTTP bridge."""
__title__ = 'Herramientas\nBIM Studio 360'
__persistentengine__ = True

import json
import os
import threading
import clr
clr.AddReference('System')
from System import Action
from System.IO import StreamReader
from System.Net import WebRequest, WebException
from System.Text import Encoding
from pyrevit import forms


class ToolPanel(forms.WPFWindow):
    def __init__(self):
        forms.WPFWindow.__init__(self, os.path.join(os.path.dirname(__file__), 'panel.xaml'))
        self.catalog = {}
        self.busy = False

    def request_async(self, route, callback, payload=None):
        if self.busy:
            return
        token = self.Token.Password
        self.busy = True
        self.Run.IsEnabled = False
        self.Connect.IsEnabled = False
        self.Output.Text = 'Procesando... Mantenga activo el documento destino en Revit.'

        def worker():
            response = None
            try:
                req = WebRequest.Create('http://127.0.0.1:8765/api/v1/' + route)
                req.Proxy = None
                req.Timeout = 180000
                req.Headers.Add('Authorization', 'Bearer ' + token)
                if payload is not None:
                    req.Method = 'POST'
                    req.ContentType = 'application/json'
                    data = Encoding.UTF8.GetBytes(json.dumps(payload))
                    req.ContentLength = data.Length
                    stream = req.GetRequestStream()
                    try:
                        stream.Write(data, 0, data.Length)
                    finally:
                        stream.Close()
                try:
                    response = req.GetResponse()
                except WebException as exc:
                    if exc.Response is None:
                        raise
                    response = exc.Response
                reader = StreamReader(response.GetResponseStream(), Encoding.UTF8)
                try:
                    result = json.loads(reader.ReadToEnd())
                finally:
                    reader.Close()
            except Exception as exc:
                result = {'error': str(exc), 'note': 'Si hubo espera agotada, compruebe Revit antes de repetir una escritura.'}
            finally:
                if response is not None:
                    response.Close()

            def finish():
                self.busy = False
                self.Run.IsEnabled = True
                self.Connect.IsEnabled = True
                if self.IsVisible:
                    callback(result)
            self.Dispatcher.Invoke(Action(finish))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def connect_click(self, sender, args):
        def loaded(data):
            if 'tools' not in data:
                self.show_result(data)
                return
            self.catalog = dict((tool['name'], tool) for tool in data['tools'])
            self.Tools.ItemsSource = sorted(self.catalog.keys())
            self.Output.Text = '{} funciones disponibles'.format(len(self.catalog))
        self.request_async('tools', loaded)

    def selection_changed(self, sender, args):
        name = self.Tools.SelectedItem
        if name not in self.catalog:
            return
        tool = self.catalog[name]
        self.Description.Text = tool['description']
        self.Schema.Text = json.dumps(tool['input_schema'], indent=2, ensure_ascii=False)
        self.Arguments.Text = '{}'

    def show_result(self, data):
        self.Output.Text = json.dumps(data, indent=2, ensure_ascii=False)

    def run_click(self, sender, args):
        name = self.Tools.SelectedItem
        if name not in self.catalog or self.busy:
            return
        try:
            arguments = json.loads(self.Arguments.Text)
            if not isinstance(arguments, dict):
                raise ValueError('Los parametros deben ser un objeto JSON.')
        except Exception as exc:
            self.Output.Text = str(exc)
            return
        confirm = self.catalog[name]['requires_confirmation']
        if confirm and not forms.alert(
            'Ejecutar {} sobre el documento activo?\n\n{}'.format(name, self.Arguments.Text),
            title='BIM Studio 360 - Revisar operacion', yes=True, no=True):
            return
        self.request_async('tools/' + name + '/execute', self.show_result,
                           {'arguments': arguments, 'confirm': confirm})


try:
    if _bimstudio_panel.IsVisible:
        _bimstudio_panel.Activate()
    else:
        _bimstudio_panel = ToolPanel()
        _bimstudio_panel.Show()
except NameError:
    _bimstudio_panel = ToolPanel()
    _bimstudio_panel.Show()
